"""paperless_proxy Celery 任务"""

import contextlib
import logging
import os
import time
from celery import shared_task
from django.conf import settings

from .services.outbox import OutboxService, OutboxDeadError
from .services.client import PaperlessClient
from .exceptions import PaperlessError
from .models import OutboxItem

logger = logging.getLogger(__name__)


@shared_task(name="paperless_proxy.process_outbox")
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
            with contextlib.suppress(OutboxDeadError):
                OutboxService.mark_failed(item, f"unexpected: {e}")
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
    with contextlib.suppress(OSError):
        os.remove(file_path)


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


@shared_task(name="paperless_proxy.check_health")
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


def _notify_admin_down(health):
    logger.error(f"paperless DOWN ({health.consecutive_failures} consecutive failures)")


def _notify_admin_recovery(health):
    logger.info("paperless RECOVERED")


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
