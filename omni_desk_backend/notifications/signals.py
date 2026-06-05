from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from events.models import Schedule, Announcement
from compliance.models import ComplianceIssue
from memos.models import Memo
from personnel.models import FamilyMember, Personnel


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


# ---- P3-1: Personnel 岗位/部门变动信号 ----


@receiver(pre_save, sender=Personnel)
def capture_personnel_pre_save(sender, instance, **kwargs):
    """捕获 Personnel 更新前的 position_id / department 旧值。"""
    if instance.pk:
        try:
            old = Personnel.objects.get(pk=instance.pk)
            instance._pre_save_snapshot = {
                "position_id": old.position_id,
                "department": old.department,
            }
        except Personnel.DoesNotExist:
            instance._pre_save_snapshot = {}
    else:
        instance._pre_save_snapshot = {}


@receiver(post_save, sender=Personnel)
def notify_personnel_position_or_department_changed(sender, instance, created, **kwargs):
    """Personnel 岗位或部门变更 → 通知本人(若有 user 关联)。"""
    if created:
        return
    snap = getattr(instance, "_pre_save_snapshot", {}) or {}
    old_pos = snap.get("position_id")
    old_dept = snap.get("department")
    new_pos = instance.position_id
    new_dept = instance.department

    if old_pos == new_pos and (old_dept or "") == (new_dept or ""):
        return  # 无变化

    user = _get_user_from_personnel(instance)
    if not user:
        return

    body_parts = []
    if old_pos != new_pos:
        body_parts.append(f"职位: {instance.position.name if instance.position else '无'}")
    if (old_dept or "") != (new_dept or ""):
        body_parts.append(f"部门: {new_dept or '无'}")

    body = "; ".join(body_parts) if body_parts else "岗位/部门已更新"
    _notify(
        user=user,
        type="position_changed",
        title="岗位/部门变动通知",
        content=body,
        link="/me/personnel",
    )


# ---- P3-2: FamilyMember 紧急联系人变更信号 ----


@receiver(post_save, sender=FamilyMember)
def notify_family_member_changed(sender, instance, created, **kwargs):
    """FamilyMember 新增或修改 → 通知 personnel 关联 user 确认。"""
    personnel = instance.personnel
    user = _get_user_from_personnel(personnel)
    if not user:
        return
    action = "新增" if created else "更新"
    _notify(
        user=user,
        type="emergency_contact",
        title=f"紧急联系人{action}确认",
        content=(
            f"您的紧急联系人 {instance.name}({instance.relationship})"
            f"{'已新增' if created else '信息已更新'},联系电话:{instance.contact_number or '无'}。"
            f"如非本人操作请尽快联系 HR。"
        ),
        link="/me/personnel",
    )
