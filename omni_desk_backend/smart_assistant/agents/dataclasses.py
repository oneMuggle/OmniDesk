"""multi-agent 执行器数据类

MultiAgentExecutor 使用的数据类定义:
- SubTaskResult: 子任务执行结果
- TaskResult: 主任务执行结果
- Event: 事件记录(EventBus 用)
- EventBus: 事件总线(简化版,用于 SSE 推送)

本模块独立于 executor.py,便于后续拆分 subtask_runner / pipeline / checkpoint 时复用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .roles import AgentRole


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
