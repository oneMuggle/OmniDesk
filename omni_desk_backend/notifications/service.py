from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Notification


class NotificationService:
    """通知服务，用于各业务模块创建通知。

    P1-3 扩展:
    - create() 新增 priority 参数(默认 NORMAL)
    - create() 新增 dedupe_key 参数:24h 窗口 + 同 user + 同 key + 未读 → 合并到原通知
    """

    DEDUPE_WINDOW = timedelta(hours=24)
    AGENT_TASK_DEDUPE_CONSTRAINT = "notif_agent_task_dedupe_uniq"

    @classmethod
    def _is_agent_task_dedupe_conflict(cls, error, type, dedupe_key):
        """仅识别本服务负责的 agent_task_result 唯一约束冲突。"""
        if type != "agent_task_result" or not dedupe_key:
            return False
        cause = getattr(error, "__cause__", None)
        constraint_name = getattr(getattr(cause, "diag", None), "constraint_name", None)
        constraint_name = constraint_name or getattr(error, "constraint_name", None)
        if constraint_name:
            return constraint_name == cls.AGENT_TASK_DEDUPE_CONSTRAINT
        message = str(cause or error).lower()
        return cls.AGENT_TASK_DEDUPE_CONSTRAINT in message

    @classmethod
    def _merge_conflicting_agent_notification(cls, user, type, dedupe_key, content):
        """按正常 dedupe 语义回读冲突行；已读或过期行不得被合并。"""
        existing = (
            Notification.objects.select_for_update()
            .filter(
                user=user,
                type=type,
                dedupe_key=dedupe_key,
                is_read=False,
                created_at__gte=timezone.now() - cls.DEDUPE_WINDOW,
            )
            .order_by("-created_at")
            .first()
        )
        if existing is None:
            return None
        existing.content = f"{existing.content}\n[追加] {content}"
        existing.save(update_fields=["content", "updated_at"])
        return existing

    @classmethod
    def create(cls, user, type, title, content, link="", priority=Notification.PRIORITY_NORMAL, dedupe_key=""):
        """创建通知,或合并到未读原通知(当 dedupe_key 非空且 24h 内存在同 key 未读通知时)。"""
        with transaction.atomic():
            if dedupe_key:
                existing = (
                    Notification.objects.select_for_update()
                    .filter(
                        user=user,
                        type=type,
                        dedupe_key=dedupe_key,
                        is_read=False,
                        created_at__gte=timezone.now() - cls.DEDUPE_WINDOW,
                    )
                    .order_by("-created_at")
                    .first()
                )
                if existing:
                    existing.content = f"{existing.content}\n[追加] {content}"
                    existing.save(update_fields=["content", "updated_at"])
                    return existing

            try:
                with transaction.atomic():
                    return Notification.objects.create(
                        user=user,
                        type=type,
                        title=title,
                        content=content,
                        link=link,
                        priority=priority,
                        dedupe_key=dedupe_key,
                    )
            except IntegrityError as error:
                if not cls._is_agent_task_dedupe_conflict(error, type, dedupe_key):
                    raise
                existing = cls._merge_conflicting_agent_notification(user, type, dedupe_key, content)
                if existing is None:
                    raise
                return existing

    @staticmethod
    def mark_read(notification_id, user):
        notification = Notification.objects.get(id=notification_id, user=user)
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
        return notification

    @staticmethod
    def batch_mark_read(notification_ids, user):
        now = timezone.now()
        return Notification.objects.filter(id__in=notification_ids, user=user).update(is_read=True, read_at=now)

    @staticmethod
    def get_unread_count(user):
        return Notification.objects.filter(user=user, is_read=False).count()
