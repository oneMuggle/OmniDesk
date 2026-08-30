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
def test_agent_task_dedupe_migration_keeps_only_matching_duplicates():
    """迁移只合并同用户、同类型、非空键的重复记录。"""
    import importlib
    from types import SimpleNamespace
    from unittest.mock import Mock

    migration = importlib.import_module(
        "notifications.migrations.0008_notification_notif_agent_task_dedupe_uniq"
    )
    first = SimpleNamespace(user_id=1, dedupe_key="agent_task:migration", content="第一条")
    duplicate = SimpleNamespace(user_id=1, dedupe_key="agent_task:migration", content="第二条")
    other_user = SimpleNamespace(user_id=2, dedupe_key="agent_task:migration", content="其他用户")
    other_type = SimpleNamespace(user_id=1, dedupe_key="agent_task:other", content="其他类型")
    rows = [first, duplicate, other_user, other_type]
    first.save = Mock()
    duplicate.delete = Mock()
    other_user.delete = Mock()
    other_type.delete = Mock()

    manager = Mock()
    manager.filter.return_value.exclude.return_value.order_by.return_value = rows
    historical_model = SimpleNamespace(objects=manager)
    apps = Mock()
    apps.get_model.return_value = historical_model

    migration.deduplicate_agent_task_notifications(apps, None)

    manager.filter.assert_called_once_with(type="agent_task_result")
    manager.filter.return_value.exclude.assert_called_once_with(dedupe_key="")
    assert first.content == "第一条\n[追加] 第二条"
    first.save.assert_called_once_with(update_fields=["content", "updated_at"])
    duplicate.delete.assert_called_once_with()
    other_user.delete.assert_not_called()
    other_type.delete.assert_not_called()


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

    def test_agent_task_dedupe_is_unique_per_user_and_type(self, regular_user_obj):
        """终态通知的唯一键按用户和任务结果类型隔离。"""
        first = NotificationService.create(
            user=regular_user_obj,
            type="agent_task_result",
            title="完成",
            content="第一次",
            dedupe_key="agent_task:42",
        )
        second = NotificationService.create(
            user=regular_user_obj,
            type="agent_task_result",
            title="完成",
            content="第二次",
            dedupe_key="agent_task:42",
        )
        assert second.pk == first.pk
        assert Notification.objects.filter(
            user=regular_user_obj, type="agent_task_result", dedupe_key="agent_task:42"
        ).count() == 1

    def test_agent_task_key_does_not_merge_other_notification_type(self, regular_user_obj):
        """相同任务键不能把不同通知类型合并。"""
        result = Notification.objects.create(
            user=regular_user_obj,
            type="agent_task_result",
            title="结果",
            content="结果内容",
            dedupe_key="agent_task:43",
        )
        other = NotificationService.create(
            user=regular_user_obj,
            type="agent_notify",
            title="提醒",
            content="提醒内容",
            dedupe_key="agent_task:43",
        )
        assert other.pk != result.pk
        assert other.type == "agent_notify"

    def test_empty_dedupe_key_is_not_unique(self, regular_user_obj):
        """空键不参与数据库唯一约束。"""
        Notification.objects.create(user=regular_user_obj, type="system", title="一", content="一")
        Notification.objects.create(user=regular_user_obj, type="system", title="二", content="二")
        assert Notification.objects.filter(user=regular_user_obj, dedupe_key="").count() == 2

    def test_non_dedupe_integrity_error_is_reraised(self, regular_user_obj, monkeypatch):
        """非终态通知的完整性错误不能被误判为去重冲突。"""
        from django.db import IntegrityError

        def fail_create(**kwargs):
            raise IntegrityError("different constraint")

        monkeypatch.setattr(Notification.objects, "create", fail_create)
        with pytest.raises(IntegrityError, match="different constraint"):
            NotificationService.create(
                user=regular_user_obj,
                type="agent_notify",
                title="提醒",
                content="内容",
                dedupe_key="agent_task:44",
            )

    def test_agent_dedupe_conflict_only_merges_matching_unread_recent_row(
        self, regular_user_obj, monkeypatch
    ):
        """唯一冲突回读必须遵守 agent_task_result 的未读/24h 语义。"""
        from django.db import IntegrityError

        old = Notification.objects.create(
            user=regular_user_obj,
            type="agent_task_result",
            title="旧",
            content="旧内容",
            dedupe_key="agent_task:45",
            is_read=True,
        )
        Notification.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        error = IntegrityError("duplicate key")
        error.constraint_name = "notif_agent_task_dedupe_uniq"

        def fail_create(**kwargs):
            raise error

        monkeypatch.setattr(Notification.objects, "create", fail_create)
        with pytest.raises(IntegrityError):
            NotificationService.create(
                user=regular_user_obj,
                type="agent_task_result",
                title="新",
                content="新内容",
                dedupe_key="agent_task:45",
            )
        old.refresh_from_db()
        assert old.content == "旧内容"
