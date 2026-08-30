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

    @staticmethod
    def create(user, type, title, content, link="", priority=Notification.PRIORITY_NORMAL, dedupe_key=""):
        """创建通知,或合并到未读原通知(当 dedupe_key 非空且 24h 内存在同 key 未读通知时)。

        R4-A13: dedupe 检查与新建统一放进同一事务,并对窗口行加 select_for_update 锁,
        避免并发下同一 user+key 在 24h 内创建出多条(生产 PostgreSQL 生效,SQLite 下为 no-op)。
        """
        with transaction.atomic():
            if dedupe_key:
                existing = (
                    Notification.objects.select_for_update()
                    .filter(
                        user=user,
                        type=type,
                        dedupe_key=dedupe_key,
                        is_read=False,
                        created_at__gte=timezone.now() - NotificationService.DEDUPE_WINDOW,
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
            except IntegrityError:
                # 另一进程可能在检查后先插入；唯一约束胜出后重新读取并合并。
                if not dedupe_key:
                    raise
                existing = Notification.objects.select_for_update().get(
                    user=user, type=type, dedupe_key=dedupe_key
                )
                existing.content = f"{existing.content}\n[追加] {content}"
                existing.save(update_fields=["content", "updated_at"])
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
