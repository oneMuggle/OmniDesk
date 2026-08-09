"""memos 定时任务(P0-2):备忘录到期提醒。

补全 ``Memo.reminder_time`` 的到期提醒闭环——此前该字段只在创建时触发一次
通知(notifications/signals.py::notify_memo_due),到期后无任何定时提醒。
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def send_due_memo_reminders():
    """扫描到期备忘录并经 NotificationService 提醒所属用户。

    筛选条件:``reminder_time <= now`` 且未完成且未提醒过。发送后置
    ``reminder_sent=True``,保证 beat 重复执行幂等(不重复轰炸)。

    改期支持:用户把 ``reminder_time`` 改到未来时,序列化器会重置
    ``reminder_sent=False``,使新时间点可再次触发(见 serializers.py)。

    Returns:
        int: 本次发送的提醒数量(供测试与日志观测)。
    """
    # 延迟导入,避免应用加载期 memos ↔ notifications 的 import 耦合
    from notifications.service import NotificationService

    from .models import Memo

    now = timezone.now()
    due_memos = Memo.objects.filter(
        reminder_time__isnull=False,
        reminder_time__lte=now,
        is_completed=False,
        reminder_sent=False,
    ).select_related("user")

    sent_count = 0
    for memo in due_memos:
        NotificationService.create(
            user=memo.user,
            type="memo_due",
            title=f"备忘提醒:{memo.title}",
            content=memo.content[:200] if memo.content else f"备忘录「{memo.title}」到提醒时间了",
            link="/memos",
            dedupe_key=f"memo_due:{memo.id}",
        )
        memo.reminder_sent = True
        memo.save(update_fields=["reminder_sent", "updated_at"])
        sent_count += 1

    if sent_count:
        logger.info("send_due_memo_reminders: 已发送 %d 条到期备忘提醒", sent_count)
    return sent_count
