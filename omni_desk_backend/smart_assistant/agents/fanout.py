"""Fan-out 分层并行执行器(FanoutRunner,S2-2)

只读 fanout:把子任务按依赖分层,同一层互不依赖的子任务并行执行,层与层之间串行。

- 依赖 = ``depends_on`` ∪ ``inputs`` 中 ``$subtask_id`` 引用(LLM 漏写 depends_on 时
  也不会在引用数据产出前开跑);推断依赖成环时退回只用 ``depends_on``。
- 每层开跑前复用 PipelineRunner 的跳过逻辑(暂停 / 取消 / resume 已完成 /
  Token 预算 / 依赖失败)。
- **只读约束由 runner_factory 保证**:执行器为每个子任务创建
  ``read_only_tools=True`` 的独立 SubTaskRunner,写工具既不出现在 schema 中,
  也会在执行时被拒绝。
- 产物写入与持久化都在调用线程按计划顺序完成;工作线程结束时关闭本线程
  的数据库连接。并发数为 1 或本层只有一个子任务时不开线程。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from observability import get_logger

from .dataclasses import EventBus, SubTaskResult
from .packet import SubTask, TaskPacket
from .pipeline import PipelineRunner
from .shared_context import SharedContext
from .subtask_runner import SubTaskRunner

logger = get_logger(__name__, "smart_assistant")


def _referenced_ids(subtask: SubTask, known_ids: set[str]) -> set[str]:
    """``inputs`` 中 ``$id`` / ``$id.field`` 引用到的其他子任务 ID。"""
    try:
        text = json.dumps(subtask.inputs, ensure_ascii=False)
    except (TypeError, ValueError):
        return set()
    refs = set()
    for match in SharedContext.REFERENCE_PATTERN.finditer(text):
        ref_id = match.group(1).split(".", 1)[0]
        if ref_id in known_ids and ref_id != subtask.id:
            refs.add(ref_id)
    return refs


def _layers_for(subtasks: list[SubTask], deps: dict[str, set[str]]) -> list[list[SubTask]] | None:
    """按依赖分层;成环时返回 None。层内保持计划中的原始顺序。"""
    remaining = {st.id for st in subtasks}
    done: set[str] = set()
    layers: list[list[SubTask]] = []
    while remaining:
        layer = [st for st in subtasks if st.id in remaining and deps[st.id] <= done]
        if not layer:
            return None
        layers.append(layer)
        for st in layer:
            remaining.discard(st.id)
            done.add(st.id)
    return layers


def build_layers(task_packet: TaskPacket) -> list[list[SubTask]]:
    """把 TaskPacket 的子任务(不含 final_synthesis)分层。"""
    subtasks = list(task_packet.subtasks)
    known = {st.id for st in subtasks}
    explicit = {st.id: set(st.depends_on) for st in subtasks}
    inferred = {st.id: explicit[st.id] | _referenced_ids(st, known) for st in subtasks}
    layers = _layers_for(subtasks, inferred)
    if layers is None:
        logger.warning("fanout 推断依赖成环,退回只按 depends_on 分层: task_id=%s", task_packet.task_id)
        layers = _layers_for(subtasks, explicit)
    if layers is None:  # TaskPacket 校验已排除显式环,这里只是兜底
        raise ValueError("无法分层,可能存在循环依赖")
    return layers


def _close_thread_db_connections() -> None:
    try:
        from django.db import connections

        connections.close_all()
    except Exception:  # pragma: no cover - 关闭失败不影响结果
        logger.debug("fanout 工作线程关闭数据库连接失败", exc_info=True)


class FanoutRunner(PipelineRunner):
    """分层并行执行器。与 PipelineRunner 共享跳过 / 持久化语义。"""

    def __init__(
        self,
        task_packet: TaskPacket,
        context: SharedContext,
        event_bus: EventBus,
        runner_factory: Callable[[], SubTaskRunner],
        max_workers: int,
        is_paused: Callable[[], bool],
        persist_subtask: Callable[[SubTask, SubTaskResult], None],
        is_cancelled: Callable[[], bool] | None = None,
        is_claim_valid: Callable[[], bool] | None = None,
    ):
        super().__init__(
            task_packet=task_packet,
            context=context,
            event_bus=event_bus,
            subtask_runner=None,  # 每个子任务由 runner_factory 创建独立实例
            is_paused=is_paused,
            persist_subtask=persist_subtask,
            is_cancelled=is_cancelled,
            is_claim_valid=is_claim_valid,
        )
        self._runner_factory = runner_factory
        self._max_workers = max(1, int(max_workers or 1))

    def run(self, resume_mode: bool = False) -> list[SubTaskResult]:
        self._resume_mode = resume_mode
        results: list[SubTaskResult] = []
        layers = build_layers(self._task_packet)
        for index, layer in enumerate(layers):
            if not self._is_claim_valid() or self._is_cancelled():
                break
            runnable: list[SubTask] = []
            for subtask in layer:
                skip_result = self._should_skip(subtask, results)
                if skip_result is not None:
                    results.append(skip_result)
                else:
                    runnable.append(subtask)
            if not runnable:
                continue
            # 复用已有事件类型(AgentEvent.EVENT_TYPE_CHOICES),不引入新类型、不需要迁移
            self._event_bus.emit(
                "supervisor.decision",
                {"decision": "fanout_layer", "layer": index, "subtask_ids": [st.id for st in runnable]},
            )
            layer_results = self._run_layer(runnable)
            for subtask, result in zip(runnable, layer_results, strict=True):
                results.append(result)
                if result.status == "success" and result.artifacts:
                    self._context.add_artifact(subtask.id, result.artifacts)
                if not self._is_claim_valid():
                    return results
                self._persist_subtask(subtask, result)
        return results

    def _run_one(self, subtask: SubTask, in_worker_thread: bool) -> SubTaskResult:
        try:
            return self._runner_factory().run_with_retry(subtask, self._context)
        except Exception:
            logger.warning("fanout 子任务执行异常: subtask_id=%s", subtask.id, exc_info=True)
            return SubTaskResult(
                subtask_id=subtask.id,
                role=subtask.role,
                output={},
                status="failed",
                error_message="子任务执行异常",
            )
        finally:
            if in_worker_thread:
                _close_thread_db_connections()

    def _run_layer(self, runnable: list[SubTask]) -> list[SubTaskResult]:
        workers = min(self._max_workers, len(runnable))
        if workers <= 1:
            return [self._run_one(subtask, in_worker_thread=False) for subtask in runnable]
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="agent-fanout") as pool:
            futures = [pool.submit(self._run_one, subtask, True) for subtask in runnable]
            return [future.result() for future in futures]
