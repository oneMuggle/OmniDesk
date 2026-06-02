from .models import Notification


class NotificationService:
    """通知服务，用于各业务模块创建通知"""

    @staticmethod
    def create(user, type, title, content, link=""):
        return Notification.objects.create(user=user, type=type, title=title, content=content, link=link)

    @staticmethod
    def mark_read(notification_id, user):
        notification = Notification.objects.get(id=notification_id, user=user)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return notification

    @staticmethod
    def batch_mark_read(notification_ids, user):
        count = Notification.objects.filter(id__in=notification_ids, user=user).update(is_read=True)
        return count

    @staticmethod
    def get_unread_count(user):
        return Notification.objects.filter(user=user, is_read=False).count()
