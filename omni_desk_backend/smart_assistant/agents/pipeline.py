"""Pipeline 顺序执行器(PipelineRunner)

负责 Pipeline 模式的完整执行流程:
1. 按拓扑顺序遍历 subtask
2. 对每个 subtask:
   - 检查是否应跳过(暂停 / resume 跳过已完成 / Token 预算耗尽 / 依赖失败)
   - 调用 SubTaskRunner 执行
   - 存储产物到 SharedContext
   - 回调持久化结果(CheckpointManager 前身)
3. 处理依赖失败(按 failure_mode: ABORT 终止 / SKIP 跳过 / 其余继续)

从 executor.py 拆出(Task 3/7),MultiAgentExecutor 通过薄委托调用,
供 pipeline / fanout / hierarchical 三种执行模式复用。
"""

from __future__ import annotations

from collections.abc import Callable

from .dataclasses import EventBus, SubTaskResult
from .shared_context import SharedContext
from .subtask_runner import SubTaskRunner
from .packet import FailureMode, SubTask, TaskPacket


# ---------------------------------------------------------------------------
# PipelineRunner 主类
# ---------------------------------------------------------------------------


class PipelineRunner:
    """Pipeline 顺序执行器:按拓扑顺序跑 subtask,处理暂停/resume 跳过/Token 预算/依赖失败"""

    def __init__(
        self,
        task_packet: TaskPacket,
        context: SharedContext,
        event_bus: EventBus,
        subtask_runner: SubTaskRunner,
        is_paused: Callable[[], bool],
        persist_subtask: Callable[[SubTask, SubTaskResult], None],
    ):
        self._task_packet = task_packet
        self._context = context
        self._event_bus = event_bus
        self._subtask_runner = subtask_runner
        self._is_paused = is_paused
        self._persist_subtask = persist_subtask

    def run(self, resume_mode: bool = False) -> list[SubTaskResult]:
        """Pipeline 模式执行(顺序执行,前一个输出是后一个输入)

        Args:
            resume_mode: 如果为 True,跳过已完成的 subtask(断点恢复用)

        Returns:
            所有 subtask 的执行结果列表
        """
        self._resume_mode = resume_mode
        results: list[SubTaskResult] = []
        execution_order = self._task_packet.get_execution_order()
        for subtask in execution_order:
            skip_result = self._should_skip(subtask, results)
            if skip_result is not None:
                results.append(skip_result)
                continue
            result = self._subtask_runner.run_with_retry(subtask, self._context)
            results.append(result)
            if result.status == "success" and result.artifacts:
                self._context.add_artifact(subtask.id, result.artifacts)
            self._persist_subtask(subtask, result)
        return results

    def _should_skip(self, subtask: SubTask, results: list[SubTaskResult]) -> SubTaskResult | None:
        """判断 subtask 是否应跳过(暂停/resume 跳过/Token 预算/依赖失败)

        返回要追加的"虚拟"SubTaskResult(表示跳过)或 None(继续执行)。
        ABORT 依赖失败在此抛 RuntimeError(与原逻辑一致)。
        """
        # 1) 暂停
        if self._is_paused():
            self._event_bus.emit(
                "subtask.skipped",
                {"subtask_id": subtask.id, "reason": "task_paused"},
            )
            return SubTaskResult(
                subtask_id=subtask.id,
                role=subtask.role,
                output={},
                status="skipped",
                error_message="任务已暂停",
            )
        # 2) resume 模式跳过已完成
        if self._resume_mode and self._context.has_artifact(subtask.id):
            self._event_bus.emit(
                "subtask.skipped",
                {"subtask_id": subtask.id, "reason": "already_completed_in_checkpoint"},
            )
            completed_artifact = self._context.get_artifact(subtask.id)
            return SubTaskResult(
                subtask_id=subtask.id,
                role=subtask.role,
                output=completed_artifact or {},
                artifacts=completed_artifact or {},
                status="success",
            )
        # 3) Token 预算
        if self._context.is_budget_exhausted():
            self._event_bus.emit(
                "subtask.skipped",
                {"subtask_id": subtask.id, "reason": "token_budget_exhausted"},
            )
            return SubTaskResult(
                subtask_id=subtask.id,
                role=subtask.role,
                output={},
                status="skipped",
                error_message="Token 预算已耗尽",
            )
        # 4) 依赖检查
        deps_failed = False
        for dep_id in subtask.depends_on:
            dep_result = next((r for r in results if r.subtask_id == dep_id), None)
            if dep_result is None or dep_result.status != "success":
                deps_failed = True
                break
        if deps_failed:
            if subtask.failure_mode == FailureMode.ABORT:
                self._event_bus.emit(
                    "task.aborted",
                    {"subtask_id": subtask.id, "reason": "dependency_failed"},
                )
                raise RuntimeError(f"Subtask '{subtask.id}' 的依赖失败,任务终止")
            elif subtask.failure_mode == FailureMode.SKIP:
                self._event_bus.emit(
                    "subtask.skipped",
                    {"subtask_id": subtask.id, "reason": "dependency_failed"},
                )
                return SubTaskResult(
                    subtask_id=subtask.id,
                    role=subtask.role,
                    output={},
                    status="skipped",
                    error_message="依赖的 subtask 失败",
                )
        return None
