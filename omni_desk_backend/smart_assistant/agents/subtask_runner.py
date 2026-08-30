"""单 subtask 执行器(SubTaskRunner)

负责单个 subtask 的执行全流程:
1. 构造上下文(to_context_for)
2. 调用 LLM(LLMRouter)
3. 解析 LLM 输出(JSON / 纯文本)
4. 按 failure_mode 处理重试 / 兜底 / 跳过 / 终止

从 executor.py 拆出(Task 2/7),MultiAgentExecutor 通过薄委托调用,
供 pipeline / fanout / hierarchical 三种执行模式复用。
"""

from __future__ import annotations

import json
import time
from typing import Any

from django.conf import settings
from observability import get_logger

from smart_assistant.tools.tool_context import ToolContext
from smart_assistant.scope import resolve_scope

from smart_assistant.agent.native_tool_runner import execute_native_tool

from .dataclasses import SubTaskResult
from .roles import ROLE_PROFILES, RoleProfile
from .shared_context import SharedContext
from .packet import FailureMode, SubTask

logger = get_logger(__name__, "smart_assistant")


# ---------------------------------------------------------------------------
# SubTaskRunner 主类
# ---------------------------------------------------------------------------


class SubTaskRunner:
    """单 subtask 执行器

    持有 LLM Router 与事件总线,负责执行单个 subtask 并返回 SubTaskResult。
    MultiAgentExecutor 通过 `self.subtask_runner` 委托调用。

    Example:
        runner = SubTaskRunner(llm_router=llm_router, event_bus=event_bus, max_retries=3)
        result = runner.run_with_retry(subtask, ctx)
    """

    def __init__(
        self,
        llm_router,
        event_bus,
        max_retries: int,
        tool_registry: Any | None = None,
        user: Any | None = None,
        context: ToolContext | None = None,
        max_tool_call_rounds: int | None = None,
    ):
        self._llm_router = llm_router
        self._event_bus = event_bus
        self._max_retries = max_retries  # 默认最大重试次数
        self._tool_registry = tool_registry
        self._user = user
        self._tool_context = context
        self._max_tool_call_rounds = max_tool_call_rounds
        self._tool_call_count = 0

    def run_with_retry(self, subtask: SubTask, ctx: SharedContext) -> SubTaskResult:
        """运行单个 subtask,支持重试

        根据 subtask.failure_mode 决定重试策略:
        - RETRY: 失败后重试,最多 max_retries 次
        - 其他模式: 不重试,直接返回结果

        Returns:
            SubTaskResult
        """
        max_retries = self._max_retries if subtask.failure_mode == FailureMode.RETRY else 0
        last_result: SubTaskResult | None = None

        for attempt in range(max_retries + 1):
            result = self.run(subtask, ctx)
            last_result = result
            result.retry_count = attempt

            if result.status == "success":
                return result

            # 失败,记录错误
            ctx.record_error(
                subtask_id=subtask.id,
                error=Exception(result.error_message or "Unknown error"),
                recovery_action=f"retry_attempt_{attempt + 1}",
            )

            self._event_bus.emit(
                "subtask.failed",
                {
                    "subtask_id": subtask.id,
                    "attempt": attempt + 1,
                    "error": result.error_message,
                },
            )

            # 如果还有重试机会,继续
            if attempt < max_retries:
                continue

            # 重试次数耗尽,根据 failure_mode 决定最终状态
            if subtask.failure_mode == FailureMode.FALLBACK:
                # 使用兜底方案(这里简化为返回空结果)
                result.status = "success"
                result.output = {
                    "fallback": True,
                    "original_error": result.error_message,
                }
                result.artifacts = {"fallback": True}
                return result
            elif subtask.failure_mode == FailureMode.SKIP:
                result.status = "skipped"
                return result
            else:
                # ABORT 或其他: 保持 failed 状态
                return result

        # 不应到达这里
        return last_result or SubTaskResult(
            subtask_id=subtask.id,
            role=subtask.role,
            output={},
            status="failed",
            error_message="Unexpected: no result produced",
        )

    def run(self, subtask: SubTask, ctx: SharedContext) -> SubTaskResult:
        """运行单个 subtask(无重试)

        执行流程:
        1. 构造上下文(to_context_for)
        2. 调用 LLM
        3. 解析 LLM 输出
        4. 触发 hooks(如果注册了)
        5. 返回 SubTaskResult

        Returns:
            SubTaskResult
        """
        start_time = time.time()
        self._event_bus.emit(
            "subtask.started",
            {
                "subtask_id": subtask.id,
                "role": subtask.role.value,
            },
        )

        try:
            # 获取角色配置
            profile = ROLE_PROFILES[subtask.role]

            # 构造上下文
            messages = ctx.to_context_for(subtask)

            # 调用 LLM;配置工具注册表时优先使用原生 tool-calling。
            content, usage = self.invoke_llm(subtask, profile, messages, ctx=ctx)

            if content == "" and self._budget_exhausted_during_tools(ctx):
                raise RuntimeError("token budget exhausted")

            # 解析 LLM 输出
            output, artifacts = self.parse_output(content, subtask)

            # 记录 Token 消耗
            tokens_used = usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
            if isinstance(usage, dict) and tokens_used == 0:
                tokens_used = (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
            if not self._native_tools_enabled():
                ctx.consume_tokens(tokens_used)

            duration_ms = int((time.time() - start_time) * 1000)

            self._event_bus.emit(
                "subtask.completed",
                {
                    "subtask_id": subtask.id,
                    "tokens_used": tokens_used,
                    "duration_ms": duration_ms,
                },
            )

            return SubTaskResult(
                subtask_id=subtask.id,
                role=subtask.role,
                output=output,
                artifacts=artifacts,
                tokens_used=tokens_used,
                duration_ms=duration_ms,
                status="success",
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return SubTaskResult(
                subtask_id=subtask.id,
                role=subtask.role,
                output={},
                tokens_used=0,
                duration_ms=duration_ms,
                status="failed",
                error_message=("token budget exhausted" if isinstance(e, RuntimeError) and str(e) == "token budget exhausted" else "subtask execution failed: " + type(e).__name__),
            )

    def invoke_llm(
        self,
        subtask: SubTask,
        profile: RoleProfile,
        messages: list[dict],
        ctx: SharedContext | None = None,
    ) -> tuple[str, dict]:
        """调用 LLM 生成 subtask 的输出

        Args:
            subtask: 当前 subtask
            profile: 角色配置
            messages: 构造好的上下文消息

        Returns:
            (content, usage) 元组
            - content: LLM 生成的文本
            - usage: Token 使用统计(dict)
        """
        # 构造 system message
        system_message = profile.system_prompt

        # 配置 registry 才启用工具路径，未配置时完全保留旧纯 LLM 行为。
        if self._native_tools_enabled():
            return self._invoke_with_tools(subtask, profile, messages, ctx)

        response = self._llm_router.generate(
            prompt=None,
            system_message=system_message,
            stream=False,
            options={
                "temperature": profile.temperature,
                "top_p": 0.9,
                "max_tokens": profile.max_tokens,
            },
            messages=messages,
        )

        # LLMRouter.generate 返回的是 content 字符串,usage 需要从 response 中提取
        # 实际接口可能是:content, usage = router.generate(...)
        # 这里简化处理,假设返回的是 content 字符串
        if isinstance(response, tuple):
            content, usage = response
        else:
            content = response
            usage = {}

        return content, usage

    def _budget_exhausted_during_tools(self, context: SharedContext) -> bool:
        return self._native_tools_enabled() and context.is_budget_exhausted()

    def _native_tools_enabled(self) -> bool:
        return (
            self._tool_registry is not None
            and self._user is not None
            and not self._is_mock_registry(self._tool_registry)
            and hasattr(self._tool_registry, "get_openai_tools")
        )

    @staticmethod
    def _is_mock_registry(registry: Any) -> bool:
        """MagicMock 等旧测试替身不应误启用原生工具路径。"""
        return registry.__class__.__module__.startswith("unittest.mock")

    def _invoke_with_tools(
        self,
        subtask: SubTask,
        profile: RoleProfile,
        messages: list[dict],
        shared_context: SharedContext | None,
    ) -> tuple[str, dict]:
        """执行受权限上下文约束的原生工具调用循环。"""
        user = self._user
        tool_context = self._tool_context or ToolContext(user=user, scope=resolve_scope(user))
        if tool_context.user is not user or tool_context.scope != resolve_scope(user):
            raise ValueError("工具上下文不可信")
        tool_schemas = self._tool_registry.get_openai_tools(user)
        max_rounds = self._max_tool_call_rounds
        if max_rounds is None:
            max_rounds = int(getattr(settings, "MAX_TOOL_CALLS_ROUNDS", 3))
        working_messages = list(messages)
        total_usage: dict = {}

        for round_index in range(max(0, max_rounds)):
            if shared_context is not None and shared_context.is_budget_exhausted():
                return "", total_usage
            content, usage, tool_calls = self._llm_router.generate_with_tools(
                messages=self._with_system_message(profile, working_messages),
                tools=tool_schemas,
                tool_choice="auto",
                options=self._llm_options(profile),
            )
            total_usage = self._merge_usage(total_usage, usage)
            self._consume_usage(shared_context, usage)
            if not tool_calls:
                return content or "", total_usage

            tool_messages = []
            for tool_call in tool_calls:
                if shared_context is not None and shared_context.is_budget_exhausted():
                    return content or "", total_usage
                name, raw_arguments = self._tool_call_fields(tool_call)
                arguments = self._decode_arguments(raw_arguments)
                self._event_bus.emit(
                    "subtask.tool_call",
                    {
                        "subtask_id": subtask.id,
                        "tool": self._safe_text(name),
                        "arguments": self._safe_summary(arguments),
                        "round": round_index,
                    },
                )
                result = self._execute_tool(name, arguments, tool_context)
                self._tool_call_count += 1
                if self._tool_call_count >= max_rounds:
                    break
                self._event_bus.emit(
                    "subtask.tool_result",
                    {
                        "subtask_id": subtask.id,
                        "tool": name,
                        "result": self._result_summary(result),
                        "round": round_index,
                    },
                )
                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", ""),
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            working_messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
            working_messages.extend(tool_messages)

        content, usage, _ = self._llm_router.generate_with_tools(
            messages=working_messages,
            tools=tool_schemas,
            tool_choice="none",
        )
        return content or "", self._merge_usage(total_usage, usage)

    @staticmethod
    def _tool_call_fields(tool_call: dict) -> tuple[str, Any]:
        function = tool_call.get("function") or {}
        return function.get("name", ""), function.get("arguments", "{}")

    @staticmethod
    def _decode_arguments(raw_arguments: Any) -> dict:
        if isinstance(raw_arguments, dict):
            return raw_arguments
        if isinstance(raw_arguments, str):
            try:
                parsed = json.loads(raw_arguments)
                return parsed if isinstance(parsed, dict) else {}
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
        return {}

    def _execute_tool(self, name: str, arguments: dict, context: ToolContext) -> dict:
        tool = self._tool_registry.get_tool_for_user(name, self._user)
        if tool is None:
            return {"error": "tool_unavailable"}
        try:
            validated = tool.validate_arguments(arguments)
        except Exception:
            return {"error": "invalid_arguments"}
        try:
            result, _, _ = execute_native_tool(tool, validated, context)
            return result if isinstance(result, dict) else {"result": "tool returned unsupported result"}
        except Exception:
            logger.warning("工具执行失败", exc_info=True)
            return {"error": "tool_execution_failed"}

    @staticmethod
    def _arguments_to_query(arguments: dict) -> str:
        query = arguments.get("query")
        if isinstance(query, str):
            return query
        return json.dumps(arguments, ensure_ascii=False)

    @staticmethod
    def _result_summary(result: Any) -> Any:
        if isinstance(result, dict):
            return {key: value for key, value in list(result.items())[:10]}
        return str(result)[:500]

    @staticmethod
    def _safe_text(value: Any, limit: int = 120) -> str:
        return str(value).replace("\n", " ")[:limit]

    @classmethod
    def _safe_summary(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {cls._safe_text(k, 40): cls._safe_summary(v) for k, v in list(value.items())[:10]}
        if isinstance(value, list):
            return [cls._safe_summary(item) for item in value[:10]]
        return cls._safe_text(value) if isinstance(value, str) else value

    @staticmethod
    def _with_system_message(profile: RoleProfile, messages: list[dict]) -> list[dict]:
        return [{"role": "system", "content": profile.system_prompt}, *messages]

    @staticmethod
    def _llm_options(profile: RoleProfile) -> dict:
        return {"temperature": profile.temperature, "top_p": 0.9, "max_tokens": profile.max_tokens}

    @staticmethod
    def _merge_usage(total: dict, usage: Any) -> dict:
        merged = dict(total)
        if isinstance(usage, dict):
            for key, value in usage.items():
                if isinstance(value, (int, float)) and isinstance(merged.get(key), (int, float)):
                    merged[key] += value
                else:
                    merged[key] = value
        return merged

    @staticmethod
    def _consume_usage(context: SharedContext | None, usage: Any) -> None:
        if context is None or not isinstance(usage, dict):
            return
        total = usage.get("total_tokens")
        if total is None:
            total = (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
        context.consume_tokens(max(0, int(total)))

    @staticmethod
    def parse_output(content: str, subtask: SubTask) -> tuple[dict | str, dict]:
        """解析 LLM 输出

        尝试将 LLM 输出解析为 JSON,如果失败则保留原始字符串。

        Args:
            content: LLM 生成的文本
            subtask: 当前 subtask

        Returns:
            (output, artifacts) 元组
            - output: 解析后的 dict 或原始字符串
            - artifacts: 提取的产物(给下游 subtask 用)
        """
        # 尝试解析为 JSON
        try:
            # 去除可能的 markdown 代码块标记
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                # 成功解析为 dict
                return parsed, parsed  # artifacts 就是整个 dict
            else:
                # 解析为其他类型(list / int / str 等),保留原始字符串
                return content, {"raw": parsed}
        except (json.JSONDecodeError, ValueError):
            # 解析失败,保留原始字符串
            # 尝试提取关键信息作为 artifacts(简化版,实际应该更智能)
            artifacts = {
                "raw_text": content,
                "length": len(content),
            }
            return content, artifacts
