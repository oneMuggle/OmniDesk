"""Outbox 写降级核心服务"""

import logging
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from datetime import timedelta

from ..models import OutboxItem

logger = logging.getLogger(__name__)


class OutboxDeadError(Exception):
    """Outbox 项达到最大重试次数,升级为死信"""


class OutboxService:
    @staticmethod
    @transaction.atomic
    def enqueue(operation: str, payload: dict, binding=None, created_by=None) -> OutboxItem:
        return OutboxItem.objects.create(
            operation=operation,
            status="pending",
            payload=payload,
            binding=binding,
            created_by=created_by,
        )

    @staticmethod
    def fetch_pending(batch_size: int = None) -> list[OutboxItem]:
        if batch_size is None:
            batch_size = settings.PAPERLESS_OUTBOX_BATCH_SIZE
        now = timezone.now()
        items = list(
            OutboxItem.objects.filter(
                status="pending",
                next_retry_at__lte=now,
            ).order_by("next_retry_at")[:batch_size]
        )
        # 标记为 syncing,避免并发 worker 重复拉取
        if items:
            OutboxItem.objects.filter(id__in=[i.id for i in items]).update(
                status="syncing",
                updated_at=now,
            )
            for item in items:
                item.status = "syncing"
        return items

    @staticmethod
    @transaction.atomic
    def mark_synced(outbox: OutboxItem) -> None:
        outbox.status = "synced"
        outbox.retry_count = 0
        outbox.last_error = ""
        outbox.save(update_fields=["status", "retry_count", "last_error", "updated_at"])

    @staticmethod
    def mark_failed(outbox: OutboxItem, error_msg: str) -> None:
        outbox.retry_count += 1
        outbox.last_error = error_msg[:2000]
        if outbox.retry_count >= outbox.max_retries:
            outbox.status = "dead"
            # 用嵌套 atomic 提交 dead 状态后,再 raise;否则外层事务会回滚
            with transaction.atomic():
                outbox.save(update_fields=["retry_count", "last_error", "status", "updated_at"])
            logger.error(f"Outbox#{outbox.id} entered dead state: {error_msg}")
            raise OutboxDeadError(f"Outbox#{outbox.id} dead: {error_msg}")
        # 指数退避:30s * 2^retry_count,上限 1 小时
        backoff = min(
            settings.PAPERLESS_OUTBOX_BASE_BACKOFF_SECONDS * (2**outbox.retry_count),
            3600,
        )
        outbox.next_retry_at = timezone.now() + timedelta(seconds=backoff)
        outbox.status = "pending"  # 退避后重新可拉取
        with transaction.atomic():
            outbox.save(
                update_fields=[
                    "retry_count",
                    "last_error",
                    "status",
                    "next_retry_at",
                    "updated_at",
                ]
            )

    @staticmethod
    def retry_dead(outbox: OutboxItem) -> OutboxItem:
        """管理员手动重试死信"""
        outbox.status = "pending"
        outbox.retry_count = 0
        outbox.next_retry_at = timezone.now()
        outbox.last_error = ""
        outbox.save(update_fields=["status", "retry_count", "next_retry_at", "last_error", "updated_at"])
        return outbox
