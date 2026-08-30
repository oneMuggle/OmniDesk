"""CheckpointManager: DB checkpoint 持久化与断点恢复的底层操作(Plan 3)

承担 MultiAgentExecutor 的 checkpoint 相关 DB 操作:
- persist_subtask: 将单个 subtask 结果持久化到 AgentSubTask DB
- set_paused / mark_running: 更新 AgentTask 状态(事务保护)
- load_completed_artifacts: 恢复时加载已完成 subtask 产物,重建 SharedContext

从 executor.py 拆出(Task 4/7),不依赖 executor,django models 均延迟导入。
静态方法供 resume_from_checkpoint classmethod 调用。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from observability import get_logger

from .dataclasses import SubTaskResult
from .shared_context import SharedContext
from .packet import SubTask

logger = get_logger(__name__, "smart_assistant")


# ---------------------------------------------------------------------------
# CheckpointManager 主类
# ---------------------------------------------------------------------------


class CheckpointManager:
    """DB checkpoint 持久化与断点恢复的底层操作(Plan 3)

    持有 agent_task_id;提供 subtask 结果持久化 / 暂停状态 / 恢复时 artifacts 重建与状态机更新。
    不依赖 executor,django models 均延迟导入。静态方法供 resume_from_checkpoint 调用。
    """

    def __init__(self, agent_task_id: str | None = None):
        self._agent_task_id = agent_task_id

    def persist_subtask(
        self,
        subtask: SubTask,
        result: SubTaskResult,
        resume_claim_id: str | None = None,
    ) -> bool:
        """将 subtask 结果持久化到 AgentSubTask DB(如果 agent_task_id 已设置)

        Args:
            subtask: 当前 subtask
            result: 执行结果
            resume_claim_id: 恢复 worker claim；传入时仅允许持有当前 claim 的 worker 写入

        Returns:
            是否实际完成持久化；claim 失效时返回 False。
        """
        if not self._agent_task_id:
            return True  # 未启用 DB 持久化

        # 映射 SubTaskResult.status → AgentSubTask.status
        # SubTaskResult 用 "success/failed/skipped"
        # AgentSubTask 用 "completed/failed/skipped/pending/running"
        status_map = {
            "success": "completed",
            "failed": "failed",
            "skipped": "skipped",
        }
        db_status = status_map.get(result.status, result.status)

        try:
            from django.db import DatabaseError, IntegrityError, transaction
            from smart_assistant.models import AgentSubTask, AgentTask

            # 恢复 worker 必须仍持有 running 状态及原 claim；校验与写入在同一事务内。
            with transaction.atomic():
                if resume_claim_id is not None:
                    agent_task = AgentTask.objects.select_for_update().get(task_id=self._agent_task_id)
                    if (
                        agent_task.status != "running"
                        or str(agent_task.resume_claim_id) != str(resume_claim_id)
                    ):
                        return False
                else:
                    agent_task = AgentTask.objects.get(task_id=self._agent_task_id)

                # 创建或更新 AgentSubTask
                agent_subtask, created = AgentSubTask.objects.update_or_create(
                    task=agent_task,
                    subtask_id=subtask.id,
                    defaults={
                        "role": subtask.role.value,
                        "objective": subtask.objective,
                        "status": db_status,
                        "depends_on": subtask.depends_on,
                        "inputs": subtask.inputs,
                        "output": result.artifacts if db_status == "completed" else None,
                        "tokens_used": result.tokens_used,
                        "retry_count": result.retry_count,
                        "error_message": result.error_message,
                        "started_at": None,  # 简化:不记录 started_at
                        "completed_at": datetime.now() if db_status == "completed" else None,
                    },
                )

            logger.debug(f"Executor: 持久化 SubTask {subtask.id} → DB (status={db_status}, created={created})")
            return True

        except (DatabaseError, IntegrityError) as e:
            # 关键 DB 错误(连接断开/约束违反)→ ERROR 级别
            # 注意: 这种情况下 subtask 结果未持久化, resume 时会重新执行
            logger.error(
                f"Executor._persist_subtask_result DB 关键错误(subtask={subtask.id}, status={db_status}): {e}",
                exc_info=True,
            )
        except Exception as e:
            # 非关键错误(字段校验等)→ WARNING,不影响主流程
            logger.warning(f"Executor._persist_subtask_result 出错: {e}", exc_info=True)
        return False

    @staticmethod
    def set_paused(task_id: str) -> None:
        """更新 AgentTask 状态为 paused(事务保护)"""
        from django.db import transaction
        from smart_assistant.models import AgentTask

        # 事务保护:确保 status 更新原子性,避免中间状态
        with transaction.atomic():
            AgentTask.objects.filter(task_id=task_id).update(status="paused")

    @staticmethod
    def load_completed_artifacts(agent_task: Any, context: SharedContext) -> int:
        """加载已完成的 subtask 产物到 SharedContext;返回 completed subtask 总数(供日志)"""
        from smart_assistant.models import AgentSubTask

        completed_subtasks = AgentSubTask.objects.filter(task=agent_task, status="completed")
        for agent_subtask in completed_subtasks:
            context.completed_subtask_ids.add(str(agent_subtask.subtask_id))
            if isinstance(agent_subtask.output, dict):
                context.add_artifact(agent_subtask.subtask_id, agent_subtask.output)
            context.consume_tokens(agent_subtask.tokens_used)
        return len(completed_subtasks)

    @staticmethod
    def mark_running(agent_task: Any) -> None:
        """更新 AgentTask 状态为 running(事务保护)"""
        from django.db import transaction

        with transaction.atomic():
            agent_task.status = "running"
            agent_task.save()
