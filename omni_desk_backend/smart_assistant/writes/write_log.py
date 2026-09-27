"""统一写 ``AgentWriteLog``（S3-1）。"""

from __future__ import annotations

from typing import Any


def record_write(
    ctx: dict,
    user,
    *,
    tool_name: str,
    target_model: str,
    target_pk: Any,
    operation: str,
    before: dict | None,
    after: dict | None,
):
    """在调用方事务内写一条写操作日志并返回。

    ``ctx`` 为 replay 注入的上下文：``task_id`` 存在时必须属于当前用户，否则抛
    ``ValueError`` 让调用方事务整体回滚（与备忘录工具原有约定一致）。
    """
    from smart_assistant.models import AgentTask, AgentWriteLog

    task = None
    task_id = ctx.get("task_id") if isinstance(ctx, dict) else None
    if task_id:
        task = AgentTask.objects.filter(task_id=task_id, user=user).first()
        if task is None:
            raise ValueError("任务不存在或不属于当前用户")
    return AgentWriteLog.objects.create(
        task=task,
        session_id=ctx.get("session_id") if isinstance(ctx, dict) else None,
        user=user,
        tool_name=(ctx.get("tool_name") if isinstance(ctx, dict) else None) or tool_name,
        target_model=target_model,
        target_pk=str(target_pk)[:64],
        operation=operation,
        before=before,
        after=after,
    )
