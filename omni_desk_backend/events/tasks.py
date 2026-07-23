"""SP4: ScheduleSwapRequest 过期清理 Celery 任务

决策 3B:TTL 48h。超期未处理的 pending 申请 → 改为 expired。
触发 SP3 信号(events.signals)自动发 schedule_swap_expired 通知给三方(申请方+接收方+HR 组)。

L3 防护:批量处理用 transaction.atomic 单条 update,失败仅 logger 不抛。

可观测性:使用 logged_task 装饰器,自动记录 celery.task.start / .success / .failure。
"""

import logging
import time
from functools import wraps

from celery import shared_task as celery_shared_task
from django.db import transaction
from django.utils import timezone

from observability import get_logger
from observability.events import CeleryEvent

from .models import ScheduleSwapRequest

logger = logging.getLogger(__name__)
_obs_logger = get_logger(__name__)


def logged_task(*celery_args, **celery_kwargs):
    """Celery 任务装饰器,自动记录 start/success/failure 事件。

    - start: 在任务入口记录 celery.task.start,含 task_name 和 task_id
    - success: 任务正常返回后记录 celery.task.success,含 duration_ms
    - failure: 任务抛异常时记录 celery.task.failure,异常向上重抛

    Args:
        *celery_args / **celery_kwargs: 透传给 celery.shared_task。

    Example:
        @logged_task()
        def my_task():
            ...
    """

    def decorator(func):
        @celery_shared_task(*celery_args, **celery_kwargs)
        @wraps(func)
        def wrapper(*args, **kwargs):
            task_name = func.__name__
            task_id = getattr(wrapper.request, "id", None)
            _obs_logger.info(
                "celery 任务开始",
                extra={
                    "event": CeleryEvent.TASK_START,
                    "task_name": task_name,
                    "task_id": task_id,
                },
            )
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                _obs_logger.error(
                    "celery 任务失败",
                    extra={
                        "event": CeleryEvent.TASK_FAILURE,
                        "task_name": task_name,
                        "task_id": task_id,
                        "error": str(exc),
                    },
                )
                raise
            duration_ms = (time.monotonic() - start) * 1000
            _obs_logger.info(
                "celery 任务成功",
                extra={
                    "event": CeleryEvent.TASK_SUCCESS,
                    "task_name": task_name,
                    "task_id": task_id,
                    "duration_ms": duration_ms,
                },
            )
            return result

        return wrapper

    return decorator


@logged_task()
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
        except Exception as exc:
            logger.warning("swap expired cleanup failed for pk=%s: %s", swap.pk, exc)

    return f"Cleaned {count} expired swap request(s)"
