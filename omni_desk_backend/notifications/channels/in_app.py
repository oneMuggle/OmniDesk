from .base import NotifyChannel
from .types import NotifyResult
from ..models import Notification
from ..service import NotificationService


class InAppChannel(NotifyChannel):
    name = "in_app"

    def send(self, *, user, type, title, content, link="", dedupe_key=""):
        kwargs = {
            "user": user,
            "type": type,
            "title": title,
            "content": content,
            "link": link,
            "priority": Notification.PRIORITY_NORMAL,
        }
        if dedupe_key:
            kwargs["dedupe_key"] = dedupe_key
        notification = NotificationService.create(**kwargs)
        return NotifyResult(
            success=True,
            message="站内通知已创建",
            notification_id=getattr(notification, "id", None),
        )
