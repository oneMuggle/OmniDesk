"""MultiAgentExecutor 多 Agent 协作执行器

实现 Pipeline 模式的完整执行流程:
1. 加载 TaskPacket
2. 创建 SharedContext
3. 按拓扑顺序遍历 subtask
4. 对每个 subtask:
   - 等待依赖完成
   - 解析 inputs 中的引用
   - 构造上下文(to_context_for)
   - 调用 LLM(LLMRouter)
   - 解析 LLM 输出(假设是 JSON 或纯文本)
   - 存储到 artifacts
   - 记录 AgentEvent
   - 触发 hooks
   - 处理失败(按 failure_mode)
5. 最终合成(如果 final_synthesis 存在)
6. 保存结果到 AgentTask 模型

当前版本仅实现 Pipeline 模式,后续 milestone 添加 Fan-out / Hierarchical。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .roles import ROLE_PROFILES, AgentRole, RoleProfile
from .shared_context import SharedContext
from .task_packet import ExecutionMode, FailureMode, SubTask, TaskPacket

# 延迟导入,避免循环依赖
# from llm_service.router import LLMRouter
# from tools.registry import ToolRegistry
# from hooks.base import HookRegistry


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class SubTaskResult:
    """子任务执行结果

    Attributes:
        subtask_id: 子任务 ID
        role: 执行角色
        output: LLM 输出(解析后的 dict 或原始字符串)
        artifacts: 提取的产物(给下游 subtask 用)
        tokens_used: 消耗的 Token 数
        duration_ms: 执行耗时(毫秒)
        status: 执行状态(success / failed / skipped)
        error_message: 错误消息(仅 failed 时)
        retry_count: 重试次数
    """

    subtask_id: str
    role: AgentRole
    output: dict | str
    artifacts: dict = field(default_factory=dict)
    tokens_used: int = 0
    duration_ms: int = 0
    status: str = "success"  # 'success' / 'failed' / 'skipped'
    error_message: str | None = None
    retry_count: int = 0


@dataclass
class TaskResult:
    """主任务执行结果

    Attributes:
        task_id: 任务 ID
        status: 任务状态(success / failed / partial)
        final_output: 最终产出物(如果有 final_synthesis)
        subtask_results: 所有 subtask 的执行结果
        total_tokens_used: 总 Token 消耗
        total_duration_ms: 总执行耗时
        error_message: 错误消息(仅 failed 时)
    """

    task_id: str
    status: str  # 'success' / 'failed' / 'partial'
    final_output: dict | str | None = None
    subtask_results: list[SubTaskResult] = field(default_factory=list)
    total_tokens_used: int = 0
    total_duration_ms: int = 0
    error_message: str | None = None


@dataclass
class Event:
    """事件记录(EventBus 用)

    Attributes:
        event_type: 事件类型(task.started / subtask.completed 等)
        payload: 事件详细数据
        timestamp: 事件时间
    """

    event_type: str
    payload: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class EventBus:
    """事件总线(简化版,用于 SSE 推送)

    实际的 SSE 推送在 view 层实现,EventBus 只负责记录事件。
    view 层通过 event_bus.get_events() 获取事件列表,推送到前端。
    """

    def __init__(self):
        self._events: list[Event] = []

    def emit(self, event_type: str, payload: dict | None = None) -> None:
        """发出事件"""
        self._events.append(
            Event(
                event_type=event_type,
                payload=payload or {},
            )
        )

    def get_events(self, since: datetime | None = None) -> list[Event]:
        """获取事件列表(可选过滤时间)"""
        if since is None:
            return list(self._events)
        return [e for e in self._events if e.timestamp > since]

    def clear(self) -> None:
        """清空事件(主要用于测试)"""
        self._events = []


# ---------------------------------------------------------------------------
# MultiAgentExecutor 主类
# ---------------------------------------------------------------------------


class MultiAgentExecutor:
    """多 Agent 协作执行器

    根据 TaskPacket 驱动任务执行,支持 Pipeline / Fan-out / Hierarchical 三种模式。
    当前版本仅实现 Pipeline 模式。

    Example:
        task_packet = TaskPacket.from_dict(supervisor_output)
        executor = MultiAgentExecutor(
            task_packet=task_packet,
            llm_router=LLMRouter(),
            tool_registry=ToolRegistry,
        )
        result = executor.execute()
        if result.status == "success":
            print(result.final_output)
    """

    MAX_RETRIES = 3  # 默认最大重试次数

    def __init__(
        self,
        task_packet: TaskPacket,
        llm_router: Any,  # LLMRouter 实例
        tool_registry: Any,  # ToolRegistry 类
        hook_registry: Any | None = None,  # HookRegistry 实例(可选)
        event_bus: EventBus | None = None,
    ):
        self.task_packet = task_packet
        self.llm_router = llm_router
        self.tool_registry = tool_registry
        self.hook_registry = hook_registry
        self.event_bus = event_bus or EventBus()
        self.context = SharedContext(
            original_query=task_packet.objective,
            user_context=task_packet.user_context,
            global_budget=task_packet.global_budget,
        )

    def execute(self) -> TaskResult:
        """执行主任务

        Returns:
            TaskResult 包含所有 subtask 的执行结果和最终产出物
        """
        start_time = time.time()
        self.event_bus.emit("task.started", {"task_id": self.task_packet.task_id})

        try:
            if self.task_packet.execution_mode == ExecutionMode.PIPELINE:
                subtask_results = self._execute_pipeline()
            elif self.task_packet.execution_mode == ExecutionMode.FANOUT:
                raise NotImplementedError("Fan-out 模式尚未实现,请等待后续 milestone")
            elif self.task_packet.execution_mode == ExecutionMode.HIERARCHICAL:
                raise NotImplementedError("Hierarchical 模式尚未实现,请等待后续 milestone")
            else:
                raise ValueError(f"未知的执行模式: {self.task_packet.execution_mode}")

            # 最终合成(如果有)
            final_output = None
            if self.task_packet.final_synthesis:
                synth_result = self._run_subtask_with_retry(
                    self.task_packet.final_synthesis, self.context
                )
                subtask_results.append(synth_result)
                if synth_result.status == "success":
                    final_output = synth_result.output

            # 判断任务状态
            failed_count = sum(1 for r in subtask_results if r.status == "failed")
            if failed_count == 0:
                status = "success"
            elif failed_count == len(subtask_results):
                status = "failed"
            else:
                status = "partial"

            total_tokens = sum(r.tokens_used for r in subtask_results)
            total_duration = int((time.time() - start_time) * 1000)

            result = TaskResult(
                task_id=self.task_packet.task_id,
                status=status,
                final_output=final_output,
                subtask_results=subtask_results,
                total_tokens_used=total_tokens,
                total_duration_ms=total_duration,
            )

            self.event_bus.emit("task.completed", {
                "task_id": self.task_packet.task_id,
                "status": status,
                "total_tokens": total_tokens,
                "total_duration_ms": total_duration,
            })

            return result

        except Exception as e:
            total_duration = int((time.time() - start_time) * 1000)
            self.event_bus.emit("task.failed", {
                "task_id": self.task_packet.task_id,
                "error": str(e),
            })
            return TaskResult(
                task_id=self.task_packet.task_id,
                status="failed",
                total_duration_ms=total_duration,
                error_message=str(e),
            )

    def _execute_pipeline(self) -> list[SubTaskResult]:
        """Pipeline 模式执行(顺序执行,前一个输出是后一个输入)

        Returns:
            所有 subtask 的执行结果列表
        """
        results: list[SubTaskResult] = []

        # 获取拓扑排序后的执行顺序
        execution_order = self.task_packet.get_execution_order()

        for subtask in execution_order:
            # 检查 Token 预算
            if self.context.is_budget_exhausted():
                self.event_bus.emit("subtask.skipped", {
                    "subtask_id": subtask.id,
                    "reason": "token_budget_exhausted",
                })
                results.append(SubTaskResult(
                    subtask_id=subtask.id,
                    role=subtask.role,
                    output={},
                    status="skipped",
                    error_message="Token 预算已耗尽",
                ))
                continue

            # 检查依赖 subtask 是否成功
            deps_failed = False
            for dep_id in subtask.depends_on:
                dep_result = next((r for r in results if r.subtask_id == dep_id), None)
                if dep_result is None or dep_result.status != "success":
                    deps_failed = True
                    break

            if deps_failed:
                # 依赖失败,根据 failure_mode 决定行为
                if subtask.failure_mode == FailureMode.ABORT:
                    self.event_bus.emit("task.aborted", {
                        "subtask_id": subtask.id,
                        "reason": "dependency_failed",
                    })
                    raise RuntimeError(
                        f"Subtask '{subtask.id}' 的依赖失败,任务终止"
                    )
                elif subtask.failure_mode == FailureMode.SKIP:
                    self.event_bus.emit("subtask.skipped", {
                        "subtask_id": subtask.id,
                        "reason": "dependency_failed",
                    })
                    results.append(SubTaskResult(
                        subtask_id=subtask.id,
                        role=subtask.role,
                        output={},
                        status="skipped",
                        error_message="依赖的 subtask 失败",
                    ))
                    continue
                # FALLBACK / RETRY: 继续执行,让 subtask 自己处理

            # 执行 subtask
            result = self._run_subtask_with_retry(subtask, self.context)
            results.append(result)

            # 存储产物
            if result.status == "success" and result.artifacts:
                self.context.add_artifact(subtask.id, result.artifacts)

        return results

    def _run_subtask_with_retry(
        self, subtask: SubTask, ctx: SharedContext
    ) -> SubTaskResult:
        """运行单个 subtask,支持重试

        根据 subtask.failure_mode 决定重试策略:
        - RETRY: 失败后重试,最多 MAX_RETRIES 次
        - 其他模式: 不重试,直接返回结果

        Returns:
            SubTaskResult
        """
        max_retries = (
            self.MAX_RETRIES if subtask.failure_mode == FailureMode.RETRY else 0
        )
        last_result: SubTaskResult | None = None

        for attempt in range(max_retries + 1):
            result = self._run_subtask(subtask, ctx)
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

            self.event_bus.emit("subtask.failed", {
                "subtask_id": subtask.id,
                "attempt": attempt + 1,
                "error": result.error_message,
            })

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

    def _run_subtask(self, subtask: SubTask, ctx: SharedContext) -> SubTaskResult:
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
        self.event_bus.emit("subtask.started", {
            "subtask_id": subtask.id,
            "role": subtask.role.value,
        })

        try:
            # 获取角色配置
            profile = ROLE_PROFILES[subtask.role]

            # 构造上下文
            messages = ctx.to_context_for(subtask)

            # 调用 LLM
            content, usage = self._invoke_llm_for_subtask(subtask, profile, messages)

            # 解析 LLM 输出
            output, artifacts = self._parse_llm_output(content, subtask)

            # 记录 Token 消耗
            tokens_used = (
                usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
            )
            ctx.consume_tokens(tokens_used)

            duration_ms = int((time.time() - start_time) * 1000)

            self.event_bus.emit("subtask.completed", {
                "subtask_id": subtask.id,
                "tokens_used": tokens_used,
                "duration_ms": duration_ms,
            })

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

    def _invoke_llm_for_subtask(
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
        response = self.llm_router.generate(
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

    def _parse_llm_output(
        self, content: str, subtask: SubTask
    ) -> tuple[dict | str, dict]:
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
