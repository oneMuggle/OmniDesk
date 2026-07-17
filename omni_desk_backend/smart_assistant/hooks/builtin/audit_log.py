"""AuditLogHook 审计日志钩子

统一写入 AgentLog(工具级) + AgentEvent(多 Agent 任务级):
- 工具执行前后 → AgentLog(每次工具调用一条)
- Subtask 生命周期 → AgentEvent(每个 subtask 的 started/completed/failed)
- Task 生命周期 → AgentEvent(任务的 started/completed/failed)

事件流 sequence 在 AgentTask 内严格递增,保证审计回放时状态一致。

Example:
    from smart_assistant.hooks.builtin.audit_log import AuditLogHook

    hook = AuditLogHook(agent_task_id=task.task_id)

    # 工具级审计(通过 HookRegistry)
    registry.register(HookEvent.POST_EXECUTE, hook, priority=10)

    # 多 Agent 事件审计(由 executor 直接调用)
    await hook.on_subtask_completed(event, subtask_db_instance)
    await hook.on_task_completed(event)
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import DatabaseError, IntegrityError

from ..base import RecoveryAction, ToolHookBase

logger = logging.getLogger(__name__)


# 关键异常类型(审计功能失效,需要立即关注)
CRITICAL_DB_ERRORS = (
    DatabaseError,  # DB 连接断开、查询超时等
    IntegrityError,  # 唯一约束违反、外键约束等
)


class AuditLogHook(ToolHookBase):
    """审计日志 Hook

    同时处理工具级审计(AgentLog)和多 Agent 事件审计(AgentEvent)。

    Attributes:
        name: Hook 名称(固定为 "audit_log")
        agent_task_id: 关联的 AgentTask UUID(可选,用于写 AgentEvent)
        _sequence_counter: 事件序列号计数器(保证递增)
    """

    name: str = "audit_log"

    def __init__(self, agent_task_id: str | None = None):
        """初始化 AuditLogHook

        Args:
            agent_task_id: 关联的 AgentTask UUID(如果写 AgentEvent 则必填)
        """
        self.agent_task_id = agent_task_id
        self._sequence_counter: int = 0

    # ------------------------------------------------------------------
    # 工具级审计(ToolHook 接口)
    # ------------------------------------------------------------------

    async def post_execute(self, tool: Any, result: Any, ctx: Any) -> Any:
        """工具执行成功后写 AgentLog

        Args:
            tool: 执行完成的工具实例(应有 name 属性)
            result: 工具返回值
            ctx: 当前上下文(应有 user / request_id / session 等属性)

        Returns:
            原始 result(不修改)
        """
        try:
            # 延迟导入,避免循环依赖
            from smart_assistant.models import AgentLog

            # 提取工具信息
            tool_name = getattr(tool, "name", tool.__class__.__name__)
            tool_input = getattr(ctx, "tool_input", {}) if hasattr(ctx, "tool_input") else {}

            # 提取用户信息
            user = getattr(ctx, "user", None)
            session = getattr(ctx, "session", None)
            request_id = getattr(ctx, "request_id", "")

            # 提取 LLM 信息(如果有)
            llm_response = ""
            if isinstance(result, dict):
                llm_response = result.get("response", str(result))
            else:
                llm_response = str(result)

            # 写 AgentLog
            await AgentLog.objects.acreate(
                session=session,
                user_query=getattr(ctx, "query", ""),
                intent=getattr(ctx, "intent", "tool_call"),
                tool_used=tool_name,
                tool_input=tool_input,
                tool_output=result if isinstance(result, dict) else {"result": result},
                llm_response=llm_response,
                tool_success=True,
            )

            logger.debug(f"AuditLogHook: 写入 AgentLog(tool={tool_name}, success=True)")

        except CRITICAL_DB_ERRORS as e:
            # 关键 DB 错误(审计功能失效)→ ERROR 级别,需要运维关注
            logger.error(
                f"AuditLogHook.post_execute DB 关键错误(审计可能失效): {e}",
                exc_info=True,
            )
        except Exception as e:
            # 非关键错误(字段校验等)→ WARNING,不影响主流程
            logger.warning(f"AuditLogHook.post_execute 出错: {e}", exc_info=True)

        return result

    async def on_failure(self, tool: Any, error: Exception, ctx: Any) -> RecoveryAction:
        """工具执行失败时写 AgentLog

        Args:
            tool: 执行失败的工具实例
            error: 抛出的异常
            ctx: 当前上下文

        Returns:
            RecoveryAction(action="ignore") — 不干预恢复策略
        """
        try:
            from smart_assistant.models import AgentLog

            tool_name = getattr(tool, "name", tool.__class__.__name__)
            tool_input = getattr(ctx, "tool_input", {}) if hasattr(ctx, "tool_input") else {}
            session = getattr(ctx, "session", None)

            await AgentLog.objects.acreate(
                session=session,
                user_query=getattr(ctx, "query", ""),
                intent=getattr(ctx, "intent", "tool_call"),
                tool_used=tool_name,
                tool_input=tool_input,
                tool_output={"error": str(error)},
                llm_response="",
                tool_success=False,
            )

            logger.debug(f"AuditLogHook: 写入 AgentLog(tool={tool_name}, success=False)")

        except CRITICAL_DB_ERRORS as e:
            logger.error(
                f"AuditLogHook.on_failure DB 关键错误(审计可能失效): {e}",
                exc_info=True,
            )
        except Exception as e:
            logger.warning(f"AuditLogHook.on_failure 出错: {e}", exc_info=True)

        return RecoveryAction(action="ignore")

    # ------------------------------------------------------------------
    # 多 Agent 事件审计(由 executor 直接调用)
    # ------------------------------------------------------------------

    async def on_subtask_started(self, event: Any, subtask_db: Any) -> None:
        """Subtask 开始时写 AgentEvent

        Args:
            event: EventBus 事件(应有 payload 属性)
            subtask_db: AgentSubTask 数据库实例
        """
        await self._write_agent_event(
            event_type="subtask.started",
            subtask_db=subtask_db,
            payload=getattr(event, "payload", {}),
        )

    async def on_subtask_completed(self, event: Any, subtask_db: Any) -> None:
        """Subtask 完成时写 AgentEvent

        Args:
            event: EventBus 事件
            subtask_db: AgentSubTask 数据库实例
        """
        await self._write_agent_event(
            event_type="subtask.completed",
            subtask_db=subtask_db,
            payload=getattr(event, "payload", {}),
        )

    async def on_subtask_failed(self, event: Any, subtask_db: Any) -> None:
        """Subtask 失败时写 AgentEvent

        Args:
            event: EventBus 事件
            subtask_db: AgentSubTask 数据库实例
        """
        payload = getattr(event, "payload", {})
        # 确保 error 信息在 payload 中
        if "error" not in payload and hasattr(event, "error"):
            payload["error"] = str(event.error)

        await self._write_agent_event(
            event_type="subtask.failed",
            subtask_db=subtask_db,
            payload=payload,
        )

    async def on_task_started(self, event: Any) -> None:
        """Task 开始时写 AgentEvent

        Args:
            event: EventBus 事件
        """
        await self._write_agent_event(
            event_type="task.started",
            subtask_db=None,
            payload=getattr(event, "payload", {}),
        )

    async def on_task_completed(self, event: Any) -> None:
        """Task 完成时写 AgentEvent

        Args:
            event: EventBus 事件
        """
        await self._write_agent_event(
            event_type="task.completed",
            subtask_db=None,
            payload=getattr(event, "payload", {}),
        )

    async def on_task_failed(self, event: Any) -> None:
        """Task 失败时写 AgentEvent

        Args:
            event: EventBus 事件
        """
        await self._write_agent_event(
            event_type="task.failed",
            subtask_db=None,
            payload=getattr(event, "payload", {}),
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _write_agent_event(
        self,
        event_type: str,
        subtask_db: Any | None,
        payload: dict,
    ) -> None:
        """写 AgentEvent 到数据库

        Args:
            event_type: 事件类型(如 "subtask.completed")
            subtask_db: AgentSubTask 实例(可选,task 级事件为 None)
            payload: 事件详细数据
        """
        if not self.agent_task_id:
            logger.warning("AuditLogHook: agent_task_id 未设置,跳过 AgentEvent 写入")
            return

        try:
            from smart_assistant.models import AgentEvent, AgentTask

            # 获取 AgentTask 实例
            agent_task = await AgentTask.objects.aget(task_id=self.agent_task_id)

            # 序列号递增
            self._sequence_counter += 1
            sequence = self._sequence_counter

            # 写 AgentEvent
            await AgentEvent.objects.acreate(
                task=agent_task,
                subtask=subtask_db,
                sequence=sequence,
                event_type=event_type,
                payload=payload,
            )

            logger.debug(f"AuditLogHook: 写入 AgentEvent(seq={sequence}, type={event_type})")

        except CRITICAL_DB_ERRORS as e:
            logger.error(
                f"AuditLogHook._write_agent_event DB 关键错误(seq={self._sequence_counter}, type={event_type}): {e}",
                exc_info=True,
            )
        except Exception as e:
            logger.warning(f"AuditLogHook._write_agent_event 出错: {e}", exc_info=True)

    def reset_sequence(self) -> None:
        """重置序列号计数器(仅测试用)"""
        self._sequence_counter = 0
