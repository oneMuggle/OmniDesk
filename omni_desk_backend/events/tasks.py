"""SP4: ScheduleSwapRequest 过期清理 Celery 任务

决策 3B:TTL 48h。超期未处理的 pending 申请 → 改为 expired。
触发 SP3 信号(events.signals)自动发 schedule_swap_expired 通知给三方(申请方+接收方+HR 组)。

L3 防护:批量处理用 transaction.atomic 单条 update,失败仅 logger 不抛。
"""
import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import ScheduleSwapRequest

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_swap_requests():
    """每小时跑一次(decision 3B TTL 48h)。

    清理流程:
    1. 查找 expires_at < now 且 status = pending 的申请
    2. 改为 status = expired
    3. 触发 SP3 信号(events.signals._on_status_change)自动发通知
    4. 返回处理数量(字符串)

    注意:不能用 .update() 批量改 status,因 signals 需触发(每个 instance.save()
    才会发通知)。逐条 save() 触发 post_save → 走 SP3 _on_status_change 路径。
    """
    now = timezone.now()
    expired_qs = ScheduleSwapRequest.objects.filter(
        status=ScheduleSwapRequest.STATUS_PENDING,
        expires_at__lt=now,
    )

    count = 0
    for swap in expired_qs:
        try:
            with transaction.atomic():
                old_status = swap.status
                swap.status = ScheduleSwapRequest.STATUS_EXPIRED
                swap.save(update_fields=["status", "updated_at"])
                # SP3 信号自动触发 _on_status_change → 发 3 通知
                count += 1
                logger.info(
                    "swap expired cleanup: pk=%s from=%s to=%s expires_at=%s",
                    swap.pk,
                    old_status,
                    swap.status,
                    swap.expires_at,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "swap expired cleanup failed for pk=%s: %s", swap.pk, exc
            )

    return f"Cleaned {count} expired swap request(s)"
