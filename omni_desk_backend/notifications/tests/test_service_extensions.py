"""P1-3 NotificationService 扩展 — TDD 测试(RED 阶段)

扩展 NotificationService:
- create() 支持 priority 参数(默认 NORMAL=2)
- create() 支持 dedupe_key 参数:24h 窗口 + 同 user + 同 key + 未读 → 合并到原通知
  (在 content 追加 '[追加] 新内容' 行)

为保持向后兼容,create() 现有调用方式不变。
"""
import pytest
from datetime import timedelta
from django.utils import timezone

from notifications.models import Notification
from notifications.service import NotificationService


@pytest.mark.django_db
class TestNotificationServicePriority:
    """priority 参数应生效。"""

    def test_create_with_priority_high(self, regular_user_obj):
        notif = NotificationService.create(
            user=regular_user_obj,
            type="schedule_change",
            title="t",
            content="c",
            priority=Notification.PRIORITY_HIGH,
        )
        assert notif.priority == Notification.PRIORITY_HIGH

    def test_create_default_priority_is_normal(self, regular_user_obj):
        notif = NotificationService.create(
            user=regular_user_obj,
            type="schedule_change",
            title="t",
            content="c",
        )
        assert notif.priority == Notification.PRIORITY_NORMAL

    def test_create_with_priority_urgent(self, regular_user_obj):
        notif = NotificationService.create(
            user=regular_user_obj,
            type="system",
            title="t",
            content="c",
            priority=Notification.PRIORITY_URGENT,
        )
        assert notif.priority == 4


@pytest.mark.django_db
class TestNotificationServiceDedupe:
    """dedupe_key 应在 24h 窗口内合并到未读原通知。"""

    def test_dedupe_key_empty_creates_new_each_time(self, regular_user_obj):
        """不提供 dedupe_key 时,每次调用都应创建新通知。"""
        n1 = NotificationService.create(
            user=regular_user_obj, type="system", title="t1", content="c1"
        )
        n2 = NotificationService.create(
            user=regular_user_obj, type="system", title="t2", content="c2"
        )
        assert n1.pk != n2.pk
        assert Notification.objects.filter(user=regular_user_obj).count() == 2

    def test_dedupe_key_merges_into_existing_unread(self, regular_user_obj):
        """同一 dedupe_key + 未读,第二次应合并(返回原对象,content 追加)。"""
        first = NotificationService.create(
            user=regular_user_obj,
            type="schedule_change",
            title="值班",
            content="原内容",
            dedupe_key="duty:42:created",
        )
        second = NotificationService.create(
            user=regular_user_obj,
            type="schedule_change",
            title="值班(略)",
            content="追加内容",
            dedupe_key="duty:42:created",
        )
        assert second.pk == first.pk
        first.refresh_from_db()
        assert "[追加] 追加内容" in first.content
        assert "原内容" in first.content
        # 通知数量仍为 1
        assert Notification.objects.filter(user=regular_user_obj).count() == 1

    def test_dedupe_key_does_not_merge_read_notifications(self, regular_user_obj):
        """已读的通知不参与合并,创建新通知。"""
        first = NotificationService.create(
            user=regular_user_obj,
            type="schedule_change",
            title="t",
            content="c1",
            dedupe_key="duty:42:created",
        )
        first.is_read = True
        first.save(update_fields=["is_read"])
        second = NotificationService.create(
            user=regular_user_obj,
            type="schedule_change",
            title="t",
            content="c2",
            dedupe_key="duty:42:created",
        )
        assert second.pk != first.pk
        assert Notification.objects.filter(user=regular_user_obj).count() == 2

    def test_dedupe_key_does_not_merge_after_24h(self, regular_user_obj):
        """超过 24h 的同 key 通知,应创建新通知(不再合并)。"""
        first = NotificationService.create(
            user=regular_user_obj,
            type="schedule_change",
            title="t",
            content="c1",
            dedupe_key="duty:42:created",
        )
        # 模拟 25 小时前
        old_time = timezone.now() - timedelta(hours=25)
        Notification.objects.filter(pk=first.pk).update(created_at=old_time)
        second = NotificationService.create(
            user=regular_user_obj,
            type="schedule_change",
            title="t",
            content="c2",
            dedupe_key="duty:42:created",
        )
        assert second.pk != first.pk

    def test_dedupe_key_isolated_per_user(self, regular_user_obj, admin_user_obj):
        """同 dedupe_key 在不同用户下应独立计数(不跨用户合并)。"""
        n1 = NotificationService.create(
            user=regular_user_obj,
            type="schedule_change",
            title="t",
            content="c1",
            dedupe_key="duty:42:created",
        )
        n2 = NotificationService.create(
            user=admin_user_obj,
            type="schedule_change",
            title="t",
            content="c2",
            dedupe_key="duty:42:created",
        )
        assert n1.pk != n2.pk
        assert n1.user == regular_user_obj
        assert n2.user == admin_user_obj
