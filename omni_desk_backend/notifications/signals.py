from django.db.models.signals import post_save
from django.dispatch import receiver

from events.models import Schedule, Announcement
from compliance.models import ComplianceIssue
from memos.models import Memo


def _notify(user, type, title, content, link=""):
    """懒加载导入 NotificationService，避免循环依赖"""
    from notifications.service import NotificationService

    NotificationService.create(user=user, type=type, title=title, content=content, link=link)


def _get_user_from_personnel(personnel):
    """通过 Personnel 获取关联的 CustomUser"""
    try:
        return personnel.user_account
    except Exception:
        return None


@receiver(post_save, sender=Schedule)
def notify_schedule_created(sender, instance, created, **kwargs):
    if not created:
        return

    if instance.duty_person:
        user = _get_user_from_personnel(instance.duty_person)
        if user:
            _notify(
                user=user,
                type="schedule_change",
                title="排班通知",
                content=f"您被安排为 {instance.duty_date} 的值班人员",
                link=f"/events/schedule/{instance.id}",
            )

    if instance.duty_leader:
        user = _get_user_from_personnel(instance.duty_leader)
        if user:
            _notify(
                user=user,
                type="schedule_change",
                title="排班通知",
                content=f"您被安排为 {instance.duty_date} 的值班领导",
                link=f"/events/schedule/{instance.id}",
            )


@receiver(post_save, sender=Announcement)
def notify_announcement_created(sender, instance, created, **kwargs):
    if not created:
        return
    from users.models import CustomUser

    all_users = CustomUser.objects.all()
    for user in all_users:
        if user.id != instance.author_id:
            _notify(
                user=user,
                type="announcement",
                title=f"新公告：{instance.title}",
                content=instance.content[:200],
                link="/announcements",
            )


@receiver(post_save, sender=ComplianceIssue)
def notify_compliance_issue_created(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.project and instance.project.manager:
        _notify(
            user=instance.project.manager,
            type="compliance_issue",
            title=f"合规问题：{instance.project.name}",
            content=f"{instance.get_severity_display()} - {instance.description[:100]}",
            link=f"/compliance/{instance.id}",
        )


@receiver(post_save, sender=Memo)
def notify_memo_due(sender, instance, created, **kwargs):
    if not created or not instance.reminder_time:
        return
    _notify(
        user=instance.user,
        type="memo_due",
        title=f"备忘录：{instance.title}",
        content=instance.content[:200] if instance.content else "您有一条新的备忘录",
        link="/memos",
    )
