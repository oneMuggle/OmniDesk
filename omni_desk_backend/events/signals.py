"""SP3: ScheduleSwapRequest 信号

决策 1C 行为:
- create → 通知接收方 + HR 组(schedule_swap_requested)
- accept(apply_swap) → 通知申请方 + HR 组(schedule_swap_approved)
- reject → 通知申请方 + HR 组(schedule_swap_rejected)
- cancel → 通知接收方 + HR 组(schedule_swap_cancelled)
- expire(由 Celery 触发,本次不处理) → 三方(schedule_swap_expired)

L3 防护:所有通知失败仅 logger.warning,绝不抛(不阻塞主流程)。
"""

import logging

from django.contrib.auth.models import Group
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import ScheduleSwapRequest

logger = logging.getLogger(__name__)


# ---- helpers ----


def _notify(user, notification_type, title, content, link=""):
    """L3 防护:try/except 全包裹,失败仅 log 不抛(沿用 v0.4.0 P3-1 模式)。"""
    from notifications.service import NotificationService

    try:
        NotificationService.create(
            user=user,
            type=notification_type,
            title=title,
            content=content,
            link=link,
        )
    except Exception as exc:
        logger.warning("swap 信号发送通知失败:user=%s type=%s err=%s", user, notification_type, exc)


def _notify_hr_group(notification_type, title, content, link=""):
    """通知 HR 组每个用户(决策 1C 知情角色)。"""
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        hr_user_ids = list(Group.objects.filter(name="Manager").values_list("user", flat=True))
        for user in User.objects.filter(pk__in=hr_user_ids, is_active=True):
            _notify(user, notification_type, title, content, link)
    except Exception as exc:
        logger.warning("swap 信号 HR 通知失败:type=%s err=%s", notification_type, exc)


def _fmt_swap(swap, action_label):
    """统一的换班通知文案生成器。"""
    requester_name = swap.requester.name
    target_name = swap.target_personnel.name
    duty_date = swap.original_schedule.duty_date
    return f"{requester_name} 与 {target_name} 之间的 {duty_date} 排班换班申请 {action_label}。原因:{swap.reason}"


# ---- pre_save: 捕获旧 status(用于 post_save 判断状态迁移) ----


@receiver(pre_save, sender=ScheduleSwapRequest)
def capture_pre_save_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = ScheduleSwapRequest.objects.get(pk=instance.pk)
            instance._pre_save_status = old.status
        except ScheduleSwapRequest.DoesNotExist:
            instance._pre_save_status = None
    else:
        instance._pre_save_status = None


# ---- post_save: 分发通知 ----


@receiver(post_save, sender=ScheduleSwapRequest)
def notify_swap_status_change(sender, instance, created, **kwargs):
    """主入口:根据 created 与 status 迁移分发 6 种通知。"""
    try:
        if created:
            _on_create(instance)
        else:
            old_status = getattr(instance, "_pre_save_status", None)
            if old_status and old_status != instance.status:
                _on_status_change(instance, old_status, instance.status)
    except Exception as exc:
        logger.warning("swap post_save 异常:pk=%s err=%s", instance.pk, exc)


def _on_create(swap):
    """创建 → 通知接收方 + HR 组。"""
    title = f"收到换班申请 from {swap.requester.name}"
    body = _fmt_swap(swap, "待您确认")
    target_user = getattr(swap.target_personnel, "user_account", None)
    if target_user:
        _notify(
            target_user,
            "schedule_swap_requested",
            title,
            body,
            link=f"/swap-requests/{swap.pk}",
        )
    _notify_hr_group(
        "schedule_swap_requested",
        f"[HR 知情] {title}",
        body,
        link=f"/swap-requests/{swap.pk}",
    )


def _on_status_change(swap, old_status, new_status):
    """状态迁移:逐 case 分发通知。"""
    link = f"/swap-requests/{swap.pk}"

    if new_status == ScheduleSwapRequest.STATUS_APPROVED:
        # 决策 1C:接收方 accept → approved,自动 apply_swap
        title = f"换班已生效 from {swap.requester.name}"
        body = _fmt_swap(swap, "已生效(双方互认)")
        requester_user = getattr(swap.requester, "user_account", None)
        if requester_user:
            _notify(
                requester_user,
                "schedule_swap_approved",
                title,
                body,
                link=link,
            )
        _notify_hr_group("schedule_swap_approved", f"[HR 知情] {title}", body, link=link)

    elif new_status == ScheduleSwapRequest.STATUS_REJECTED:
        title = f"换班被拒绝 from {swap.requester.name}"
        body = _fmt_swap(swap, "接收方已拒绝")
        requester_user = getattr(swap.requester, "user_account", None)
        if requester_user:
            _notify(
                requester_user,
                "schedule_swap_rejected",
                title,
                body,
                link=link,
            )
        _notify_hr_group("schedule_swap_rejected", f"[HR 知情] {title}", body, link=link)

    elif new_status == ScheduleSwapRequest.STATUS_CANCELLED:
        title = f"换班已撤销 by {swap.requester.name}"
        body = _fmt_swap(swap, "申请方已撤销")
        target_user = getattr(swap.target_personnel, "user_account", None)
        if target_user:
            _notify(
                target_user,
                "schedule_swap_cancelled",
                title,
                body,
                link=link,
            )
        _notify_hr_group("schedule_swap_cancelled", f"[HR 知情] {title}", body, link=link)

    elif new_status == ScheduleSwapRequest.STATUS_EXPIRED:
        # 决策 3B:Celery 任务触发,通知三方
        title = f"换班申请已超时 #{swap.pk}"
        body = _fmt_swap(swap, "已超时失效(48h 未处理)")
        for personnel_attr in ("requester", "target_personnel"):
            user = getattr(getattr(swap, personnel_attr), "user_account", None)
            if user:
                _notify(user, "schedule_swap_expired", title, body, link=link)
        _notify_hr_group("schedule_swap_expired", f"[HR 知情] {title}", body, link=link)
