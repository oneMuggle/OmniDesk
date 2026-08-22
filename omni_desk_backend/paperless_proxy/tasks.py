"""paperless_proxy Celery 任务"""

import os
import time
from celery import shared_task
from django.conf import settings
from django.db.models import Q

from observability import get_logger
from notifications.models import Notification
from notifications.service import NotificationService
from users.models import CustomUser

from .services.outbox import OutboxService, OutboxDeadError
from .services.client import PaperlessClient
from .exceptions import PaperlessError
from .models import OutboxItem

logger = get_logger(__name__, "paperless_proxy.tasks")


@shared_task(
    name="paperless_proxy.process_outbox",
    task_time_limit=360,  # 硬超时 6 分钟：单批可能上传多个文件，比 execute_agent_task 放宽
    task_soft_time_limit=300,  # 软超时 5 分钟（触发 SoftTimeLimitExceeded）
)
def process_paperless_outbox():
    """处理 Outbox 中的 pending 项,推送到 paperless"""
    items = OutboxService.fetch_pending()
    if not items:
        return {"processed": 0, "succeeded": 0, "failed": 0}

    client = PaperlessClient()
    succeeded = 0
    failed = 0
    for item in items:
        try:
            if item.operation == "upload":
                _process_upload(item, client)
            elif item.operation == "delete":
                _process_delete(item, client)
            elif item.operation == "update_metadata":
                _process_update_metadata(item, client)
            else:
                raise PaperlessError(f"unknown operation: {item.operation}")
            # delete 操作通过 binding.delete() 联动 CASCADE 删 outbox 本体,
            # mark_synced 需跳过已不存在的行,避免 _prepare_related_fields_for_save 报错
            if OutboxItem.objects.filter(pk=item.pk).exists():
                OutboxService.mark_synced(item)
            succeeded += 1
        except PaperlessError as e:
            try:
                OutboxService.mark_failed(item, str(e))
            except OutboxDeadError:
                logger.error(f"Outbox#{item.id} dead: {e}")
            failed += 1
        except Exception as e:
            logger.exception(f"Outbox#{item.id} unexpected error: {e}")
            try:
                OutboxService.mark_failed(item, f"unexpected: {e}")
            except OutboxDeadError:
                pass
            failed += 1

    return {"processed": len(items), "succeeded": succeeded, "failed": failed}


def _process_upload(item, client: PaperlessClient) -> None:
    payload = item.payload
    file_path = payload["file_path"]
    if not os.path.exists(file_path):
        raise PaperlessError(f"pending file not found: {file_path}")
    with open(file_path, "rb") as f:
        result = client.upload(
            file_obj=f,
            filename=payload["filename"],
            title=payload.get("title", payload["filename"]),
            owner=payload.get("owner"),
            correspondent=payload.get("correspondent"),
            document_type=payload.get("document_type"),
            tags=payload.get("tags"),
        )
    if item.binding and item.binding.paperless_id is None:
        item.binding.paperless_id = result["id"]
        item.binding.paperless_checksum = result.get("checksum", "")
        item.binding.save(update_fields=["paperless_id", "paperless_checksum", "updated_at"])
    # 删除本地待同步文件
    try:
        os.remove(file_path)
    except OSError:
        pass


def _process_delete(item, client: PaperlessClient) -> None:
    paperless_id = item.binding.paperless_id if item.binding else item.payload.get("paperless_id")
    if paperless_id is None:
        raise PaperlessError("binding not yet synced, cannot delete")
    client.delete(paperless_id)
    if item.binding:
        item.binding.delete()  # CASCADE 删 outbox


def _process_update_metadata(item, client: PaperlessClient) -> None:
    binding = item.binding
    if not binding or binding.paperless_id is None:
        raise PaperlessError("binding not yet synced, cannot update_metadata")
    client.update_metadata(binding.paperless_id, item.payload)
    # 回写本地 binding
    fields_to_save = []
    if "title" in item.payload:
        binding.title = item.payload["title"]
        fields_to_save.append("title")
    if "extra_metadata" in item.payload:
        binding.extra_metadata = item.payload["extra_metadata"]
        fields_to_save.append("extra_metadata")
    if fields_to_save:
        fields_to_save.append("updated_at")
        binding.save(update_fields=fields_to_save)


@shared_task(
    name="paperless_proxy.check_health",
    task_time_limit=60,  # 硬超时 1 分钟：30s 周期健康检查应快速返回，HTTP 挂起时兜底
    task_soft_time_limit=30,  # 软超时 30 秒（触发 SoftTimeLimitExceeded）
)
def check_paperless_health():
    """定时检查 paperless 健康状态"""
    from .models import PaperlessHealth

    health = PaperlessHealth.get_singleton()
    client = PaperlessClient()
    is_up = client.health_check()
    threshold = settings.PAPERLESS_HEALTH_FAILURE_THRESHOLD
    if is_up:
        was_unhealthy = not health.is_healthy
        health.is_healthy = True
        health.consecutive_failures = 0
        health.last_error = ""
        health.save()
        if was_unhealthy:
            _notify_admin_recovery(health)
    else:
        health.consecutive_failures += 1
        if health.consecutive_failures >= threshold and health.is_healthy:
            health.is_healthy = False
            health.save()
            _notify_admin_down(health)
        else:
            health.save(update_fields=["consecutive_failures", "last_check_at"])
    return {"is_healthy": health.is_healthy, "consecutive_failures": health.consecutive_failures}


def _iter_admin_users():
    """全体管理员(superuser 或 Admin 组),去重。"""
    return CustomUser.objects.filter(Q(is_superuser=True) | Q(groups__name="Admin")).distinct().order_by("id")


def _notify_admin_down(health):
    """paperless 连续失败越过阈值 → 紧急通知全体管理员(P0-H)。

    dedupe_key 按 health 单例行 id:24h 内同一下降事件的重复通知会被
    NotificationService 合并到原通知,避免告警风暴。
    """
    logger.error(f"paperless DOWN ({health.consecutive_failures} consecutive failures)")
    for admin in _iter_admin_users():
        NotificationService.create(
            user=admin,
            type="paperless_down",
            title="Paperless 服务不可用",
            content=(
                f"Paperless 服务连续 {health.consecutive_failures} 次健康检查失败,"
                f"已标记为不可用。最后错误:{health.last_error or '无'}。请尽快排查。"
            ),
            dedupe_key=f"paperless_down:{health.id}",
            priority=Notification.PRIORITY_URGENT,
        )


def _notify_admin_recovery(health):
    """paperless 从不可用恢复 → 通知全体管理员(P0-H)。"""
    logger.info("paperless RECOVERED")
    for admin in _iter_admin_users():
        NotificationService.create(
            user=admin,
            type="paperless_recovered",
            title="Paperless 服务已恢复",
            content="Paperless 服务健康检查已恢复正常。",
            dedupe_key=f"paperless_recovered:{health.id}",
            priority=Notification.PRIORITY_NORMAL,
        )


@shared_task(name="paperless_proxy.cleanup_cache")
def cleanup_paperless_cache():
    """清理过期的 paperless 本地缓存文件"""
    cache_dir = os.path.join(settings.MEDIA_ROOT, settings.PAPERLESS_CACHE_DIR)
    if not os.path.exists(cache_dir):
        return {"deleted": 0}
    max_age_seconds = settings.PAPERLESS_CACHE_MAX_AGE_DAYS * 86400
    now = time.time()
    deleted = 0
    for fname in os.listdir(cache_dir):
        fpath = os.path.join(cache_dir, fname)
        if not os.path.isfile(fpath):
            continue
        mtime = os.path.getmtime(fpath)
        if now - mtime > max_age_seconds:
            try:
                os.remove(fpath)
                deleted += 1
            except OSError:
                pass
    return {"deleted": deleted, "cache_dir": cache_dir}
