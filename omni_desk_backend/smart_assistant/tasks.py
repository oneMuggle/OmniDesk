from celery import shared_task
from django.conf import settings

from ragflow_service.client import RagflowClient, RagflowClientError

from observability import get_logger
from notifications.service import NotificationService

logger = get_logger(__name__, "smart_assistant")


def calculate_agent_task_time_limits(task):
    """根据任务包、LLM 超时和配置计算 Celery soft/hard time limit。"""
    packet = task.task_packet if hasattr(task, "task_packet") else task or {}
    packet = packet if isinstance(packet, dict) else {}
    steps = len(packet.get("subtasks", [])) + (1 if packet.get("final_synthesis") else 0)
    llm_timeout = max(1, int(getattr(settings, "LLM_REQUEST_TIMEOUT_SECONDS", 120)))
    coefficient = max(1, int(getattr(settings, "AGENT_TASK_RETRY_COEFFICIENT", 4)))
    configured_max = max(llm_timeout, int(getattr(settings, "AGENT_TASK_MAX_SECONDS", 1800)))
    packet_timeout = packet.get("timeout_seconds")
    requested = (
        int(packet_timeout) if isinstance(packet_timeout, (int, float)) and packet_timeout > 0 else configured_max
    )
    budget = getattr(task, "global_budget", 0) or 0
    budget_factor = max(1, min(4, (int(budget) + 19999) // 20000)) if budget else 1
    soft_limit = min(
        configured_max,
        requested,
        max(llm_timeout, steps * llm_timeout * coefficient * budget_factor),
    )
    return soft_limit, min(configured_max + 60, soft_limit + 60)


def dispatch_agent_task(task):
    """按任务包计算超时后派发 Celery 任务。"""
    soft_limit, hard_limit = calculate_agent_task_time_limits(task)
    return execute_agent_task.apply_async(
        args=[str(task.task_id)],
        soft_time_limit=soft_limit,
        time_limit=hard_limit,
    )


_AGENT_TASK_NOTIFICATION_STATUSES = {"completed", "partial", "failed", "cancelled"}
_AGENT_TASK_NOTIFICATION_LABELS = {
    "completed": "已完成",
    "partial": "部分完成",
    "failed": "失败",
    "cancelled": "已取消",
}


def _notify_agent_task_result(task, status):
    """为已进入终态的 AgentTask 创建一次安全的站内结果通知。"""
    if status not in _AGENT_TASK_NOTIFICATION_STATUSES:
        return
    try:
        NotificationService.create(
            user=task.user,
            type="agent_task_result",
            title="智能助手任务结果",
            content=f"任务 {str(task.task_id)[:8]} {_AGENT_TASK_NOTIFICATION_LABELS[status]}。",
            dedupe_key=f"agent_task:{task.task_id}",
        )
    except Exception:
        logger.exception("智能助手任务结果通知失败: task_id=%s status=%s", task.task_id, status)


def _schedule_agent_task_notification(task, status, transaction):
    """在状态事务提交后安全发送通知，避免通知失败回滚业务状态。"""
    transaction.on_commit(lambda: _notify_agent_task_result(task, status))


@shared_task(
    autoretry_for=(RagflowClientError,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 3},
    task_time_limit=300,  # 硬超时 5 分钟：整文件读内存 + 上传 Ragflow 兜底
    task_soft_time_limit=240,  # 软超时 4 分钟（触发 SoftTimeLimitExceeded）
)
def process_document_embedding(document_id):
    """异步处理文档向量化：上传到 Ragflow 并触发解析。

    使用 RagflowClient 统一封装 API 调用。
    """
    from smart_assistant.models import KnowledgeBaseDocument
    from ragflow_service.models import RagflowConfig
    from django.conf import settings

    try:
        doc = KnowledgeBaseDocument.objects.get(id=document_id)
        doc.embedding_status = "processing"
        doc.save(update_fields=["embedding_status"])

        config = RagflowConfig.objects.filter(is_active=True).first()
        if not config:
            raise ValueError("Ragflow 配置未激活")

        dataset_id = getattr(settings, "SMART_ASSISTANT_DATASET_ID", None)
        if not dataset_id:
            raise ValueError("SMART_ASSISTANT_DATASET_ID 未配置")

        client = RagflowClient(api_endpoint=config.api_endpoint, api_key=config.api_key)
        try:
            # Step 1: 上传文档到 Ragflow dataset
            with doc.file.open("rb") as f:
                file_content = f.read()

            upload_result = client.upload_document(
                dataset_id=dataset_id,
                file_name=doc.file.name,
                file_content=file_content,
            )

            # Ragflow 返回文档 ID
            doc_infos = upload_result if isinstance(upload_result, list) else [upload_result]
            if not doc_infos:
                raise ValueError("文档上传到 Ragflow 失败，未返回文档信息")

            ragflow_doc_id = doc_infos[0].get("id") or doc_infos[0].get("doc_id")
            if not ragflow_doc_id:
                raise ValueError("未能获取 Ragflow 文档 ID")

            doc.ragflow_document_id = ragflow_doc_id
            doc.save(update_fields=["ragflow_document_id"])

            # Step 2: 触发文档解析
            client.parse_documents(dataset_id=dataset_id, document_ids=[ragflow_doc_id])

            doc.embedding_status = "completed"
            doc.save(update_fields=["embedding_status"])
        finally:
            client.close()

    except KnowledgeBaseDocument.DoesNotExist:
        logger.debug(
            "smart_assistant.tasks.document_gone",
            extra={"event": "smart_assistant.tasks.document_gone", "document_id": document_id},
        )
    except Exception as exc:
        logger.error("文档向量化失败: type=%s code=%s", type(exc).__name__, getattr(exc, "code", "unknown"))
        from smart_assistant.models import KnowledgeBaseDocument

        try:
            doc = KnowledgeBaseDocument.objects.get(id=document_id)
            doc.embedding_status = "failed"
            doc.content_text = "文档向量化失败。"
            doc.save(update_fields=["embedding_status", "content_text"])
        except KnowledgeBaseDocument.DoesNotExist:
            logger.debug(
                "smart_assistant.tasks.mark_failed_doc_gone",
                extra={"event": "smart_assistant.tasks.mark_failed_doc_gone", "document_id": document_id},
            )
        raise


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={"max_retries": 2},
    task_time_limit=300,  # 硬超时 5 分钟
    task_soft_time_limit=240,  # 软超时 4 分钟(触发 SoftTimeLimitExceeded)
)
def execute_agent_task(task_id: str):
    """异步执行多 Agent 协作任务

    流程:
    1. 从数据库加载 AgentTask
    2. 构造 TaskPacket
    3. 创建 MultiAgentExecutor
    4. 执行任务
    5. 保存结果到数据库
    6. 记录 AgentEvent(供 SSE 推送)

    Args:
        task_id: AgentTask 的 task_id(UUID 字符串)
    """
    from django.utils import timezone
    from django.db import transaction

    from smart_assistant.models import AgentSubTask, AgentTask
    from smart_assistant.agents.packet import TaskPacket
    from smart_assistant.agents.executor import MultiAgentExecutor
    from smart_assistant.agents.dataclasses import PersistentEventBus
    from llm_service.router import get_router
    from smart_assistant.tools.registry import ToolRegistry

    event_bus = PersistentEventBus(agent_task_id=task_id)

    try:
        # 原子抢占：只有待执行/暂停任务可以进入 worker；重复投递直接幂等返回。
        with transaction.atomic():
            task = AgentTask.objects.select_for_update().get(task_id=task_id)
            if task.status in {"completed", "failed", "partial", "cancelled"}:
                return {"task_id": str(task.task_id), "status": task.status, "total_tokens": task.tokens_used}
            if task.status == "running":
                return {"task_id": str(task.task_id), "status": "running", "total_tokens": task.tokens_used}
            was_paused = task.status == "paused"
            # resume_from_checkpoint 自己负责在锁内将 paused → running；提前改状态
            # 会让它误判为并发恢复并拒绝执行。
            if not was_paused:
                task.status = "running"
                task.started_at = task.started_at or timezone.now()
                task.save(update_fields=["status", "started_at"])

        if was_paused:
            result = MultiAgentExecutor.resume_from_checkpoint(
                task_id=task_id,
                llm_router=get_router(),
                tool_registry=ToolRegistry,
                event_bus=event_bus,
            )
        else:
            task_packet = TaskPacket.from_dict(task.task_packet, task_id=str(task.task_id))
            executor = MultiAgentExecutor(
                task_packet=task_packet,
                llm_router=get_router(),
                tool_registry=ToolRegistry,
                event_bus=event_bus,
                agent_task_id=task_id,
                user=task.user,
            )
            result = executor.execute()
        persisted_status = {
            "success": "completed",
            "partial": "partial",
            "failed": "failed",
            "paused": "paused",
            "cancelled": "cancelled",
            "rejected": "failed",
        }.get(result.status, "failed")

        with transaction.atomic():
            locked_task = AgentTask.objects.select_for_update().get(task_id=task_id)
            if was_paused and (
                result.claim_lost
                or result.resume_claim_id != str(locked_task.resume_claim_id)
                or locked_task.status != "running"
            ):
                return {
                    "task_id": str(locked_task.task_id),
                    "status": locked_task.status,
                    "total_tokens": locked_task.tokens_used,
                }
            # resume_from_checkpoint owns initialization-failure convergence. Do
            # not turn its already-terminal failed state into task.completed.
            if result.status == "failed" and locked_task.status == "failed":
                return {
                    "task_id": str(locked_task.task_id),
                    "status": "failed",
                    "total_tokens": locked_task.tokens_used,
                }
            if locked_task.status in {"cancelled", "paused"}:
                terminal_type = "task.cancelled" if locked_task.status == "cancelled" else "task.paused"
                event_bus.emit(
                    terminal_type,
                    {"task_id": str(locked_task.task_id), "status": locked_task.status},
                )
                if locked_task.status == "cancelled":
                    _schedule_agent_task_notification(locked_task, "cancelled", transaction)
                return {
                    "task_id": str(locked_task.task_id),
                    "status": locked_task.status,
                    "total_tokens": locked_task.tokens_used,
                }
            locked_task.status = persisted_status
            locked_task.tokens_used = result.total_tokens_used
            locked_task.completed_at = timezone.now()
            locked_task.final_output = (
                result.final_output
                if isinstance(result.final_output, (dict, list))
                else {"raw": result.final_output}
                if result.final_output
                else None
            )
            locked_task.save(update_fields=["status", "tokens_used", "completed_at", "final_output"])
            event_type = "task.failed" if persisted_status == "failed" else "task.completed"
            event_payload = {
                "task_id": str(locked_task.task_id),
                "status": persisted_status,
                "total_tokens": result.total_tokens_used,
                "final_output": locked_task.final_output,
                "dropped_events": event_bus.persistence_failure_count,
            }
            if persisted_status == "failed":
                failure_reason = result.error_message or "任务执行失败"
                event_payload["error"] = failure_reason
                event_payload["reason"] = failure_reason
            elif persisted_status == "partial":
                event_payload["reason"] = result.error_message or "任务部分完成"
            event_bus.emit(event_type, event_payload)
            _schedule_agent_task_notification(locked_task, persisted_status, transaction)
            subtask_objs = {
                str(obj.subtask_id): obj for obj in AgentSubTask.objects.select_for_update().filter(task=locked_task)
            }
            now = timezone.now()
            updates = []
            for subtask_result in result.subtask_results:
                subtask_obj = subtask_objs.get(str(subtask_result.subtask_id))
                if subtask_obj is None:
                    continue
                subtask_obj.status = "completed" if subtask_result.status == "success" else subtask_result.status
                subtask_obj.output = (
                    subtask_result.output
                    if isinstance(subtask_result.output, (dict, list))
                    else {"raw": subtask_result.output}
                )
                subtask_obj.tokens_used = subtask_result.tokens_used
                subtask_obj.completed_at = now
                subtask_obj.retry_count = subtask_result.retry_count
                subtask_obj.error_message = subtask_result.error_message
                updates.append(subtask_obj)
            if updates:
                AgentSubTask.objects.bulk_update(
                    updates,
                    ["status", "output", "tokens_used", "completed_at", "retry_count", "error_message"],
                )

        return {
            "task_id": str(task.task_id),
            "status": persisted_status,
            "total_tokens": result.total_tokens_used,
        }

    except AgentTask.DoesNotExist:
        logger.info(
            "smart_assistant.tasks.agent_task_gone",
            extra={"event": "smart_assistant.tasks.agent_task_gone", "task_id": task_id},
        )
        return None
    except Exception:
        with transaction.atomic():
            try:
                task = AgentTask.objects.select_for_update().get(task_id=task_id)
            except AgentTask.DoesNotExist:
                logger.info(
                    "smart_assistant.tasks.cleanup_task_gone",
                    extra={"event": "smart_assistant.tasks.cleanup_task_gone", "task_id": task_id},
                )
                return None
            if task.status != "cancelled" and task.status not in {"completed", "failed", "partial", "paused"}:
                task.status = "failed"
                task.completed_at = timezone.now()
                task.save(update_fields=["status", "completed_at"])
                event_bus.emit(
                    "task.failed",
                    {
                        "task_id": str(task.task_id),
                        "status": "failed",
                        "error": "agent task execution failed",
                        "reason": "agent task execution failed",
                        "final_output": task.final_output,
                        "total_tokens": task.tokens_used,
                        "dropped_events": event_bus.persistence_failure_count,
                    },
                )
                _schedule_agent_task_notification(task, "failed", transaction)
        raise


@shared_task
def send_daily_digests():
    """智能助手每日晨报派发任务(工作日 8:30 由 beat 触发,见 CELERY_BEAT_SCHEDULE)。

    主动循环(proactivity MVP)的推送环节。性能修复:原实现对所有目标用户
    串行跑完整编排链路(每用户数秒至十余秒),50 用户易超 10 分钟且 8:30
    集中锤击本地 LLM。现改为派发模式——主任务仅遍历目标用户并为每个用户
    dispatch ``send_single_digest`` 子任务,由 Celery worker 并发消费,
    单用户失败在子任务内隔离,不影响其余用户。

    目标用户(MVP 范围):所有 ``is_active=True`` 且 ``is_staff=True`` 的用户。
    TODO(后续):改为按 NotificationPreference 偏好设置订阅/退订,
    并支持用户自选晨报包含的模块。

    返回:{"dispatched": <派发子任务数>, "date": <ISO 日期>}
    """
    from django.contrib.auth import get_user_model
    from django.utils import timezone

    User = get_user_model()
    today = timezone.localdate()
    user_ids = list(User.objects.filter(is_active=True, is_staff=True).values_list("id", flat=True))

    for user_id in user_ids:
        send_single_digest.delay(user_id)

    logger.info("每日晨报子任务派发完成: dispatched=%s date=%s", len(user_ids), today.isoformat())
    return {"dispatched": len(user_ids), "date": today.isoformat()}


@shared_task
def send_single_digest(user_id):
    """为单个用户生成晨报并写入 Notification(由 ``send_daily_digests`` 派发)。

    失败隔离约定(自身 try/except 记录 success/failure,不向 Celery 抛异常,
    避免无意义的任务失败重试):
    - 用户不存在 → 记 warning 日志,返回 success=False;
    - ``generate_daily_digest`` 返回 None(生成失败)→ 记日志,跳过,不写通知;
    - 其他异常(写通知失败等)→ logger.exception 记录,返回 success=False。

    去重:通过 ``NotificationService.create`` 的 dedupe_key(按日期粒度,
    Service 内部再按 user 过滤)做当日去重,beat 重投/子任务重复执行
    不会给用户发第二条晨报。
    """
    from django.contrib.auth import get_user_model
    from django.utils import timezone

    from notifications.service import NotificationService
    from smart_assistant.digest import generate_daily_digest

    User = get_user_model()
    today = timezone.localdate()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning("晨报推送跳过,用户不存在: user_id=%s date=%s", user_id, today.isoformat())
        return {"user_id": user_id, "success": False, "reason": "user_not_found"}

    try:
        markdown = generate_daily_digest(user, today=today)
        if not markdown:
            logger.warning("晨报生成失败,已跳过: user=%s date=%s", user.username, today.isoformat())
            return {"user_id": user_id, "success": False, "reason": "generate_failed"}
        NotificationService.create(
            user=user,
            type="system",
            title=f"智能助手每日晨报（{today.isoformat()}）",
            content=markdown,
            # 去重键按日期粒度:NotificationService 会再按 user 过滤,同键 24h 内合并
            dedupe_key=f"smart_assistant_daily_digest:{today.isoformat()}",
        )
        logger.info("晨报推送成功: user=%s date=%s", user.username, today.isoformat())
        return {"user_id": user_id, "success": True}
    except Exception:
        logger.exception("晨报推送失败: user=%s date=%s", user.username, today.isoformat())
        return {"user_id": user_id, "success": False, "reason": "exception"}


@shared_task(name="cleanup_office_tmp_files")
def cleanup_office_tmp_files():
    """定期清理 tmp_office 过期生成文件。"""
    from .tools_io import cleanup_expired_files

    removed = cleanup_expired_files()
    logger.info("已清理过期 office 临时文件: %s", removed)
    return removed
