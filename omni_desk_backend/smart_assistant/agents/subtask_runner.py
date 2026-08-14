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

from observability import get_logger

from .dataclasses import SubTaskResult
from .roles import ROLE_PROFILES, RoleProfile
from .shared_context import SharedContext
from .task_packet import FailureMode, SubTask

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

    def __init__(self, llm_router, event_bus, max_retries: int):
        self._llm_router = llm_router
        self._event_bus = event_bus
        self._max_retries = max_retries  # 默认最大重试次数

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

            # 调用 LLM
            content, usage = self.invoke_llm(subtask, profile, messages)

            # 解析 LLM 输出
            output, artifacts = self.parse_output(content, subtask)

            # 记录 Token 消耗
            tokens_used = usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
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
                error_message=str(e),
            )

    def invoke_llm(
        self,
        subtask: SubTask,
        profile: RoleProfile,
        messages: list[dict],
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

        # 调用 LLMRouter
        # 注意:LLMRouter.generate 返回 (content, usage) 元组
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
