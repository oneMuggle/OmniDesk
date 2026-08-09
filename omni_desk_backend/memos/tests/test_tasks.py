"""Tests for memos.tasks — P0-2 备忘录到期提醒定时任务."""

from datetime import timedelta

import pytest
from django.utils import timezone

from notifications.models import Notification
from users.models import CustomUser

from ..models import Memo
from ..tasks import send_due_memo_reminders

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username="memo_task_user", password="pass123")


def _make_memo(user, reminder_time, **kwargs):
    return Memo.objects.create(
        user=user,
        title=kwargs.pop("title", "测试备忘"),
        content=kwargs.pop("content", "备忘内容"),
        reminder_time=reminder_time,
        **kwargs,
    )


def _task_notifs(user):
    """仅统计本任务产生的通知。

    创建信号 notify_memo_due 在 memo 创建时也会发一条 memo_due 通知(既有行为,
    dedupe_key 为空);本任务的通知带 dedupe_key="memo_due:<id>",据此隔离。
    """
    return Notification.objects.filter(user=user, dedupe_key__startswith="memo_due:")


class TestSendDueMemoReminders:
    """send_due_memo_reminders 扫描到期备忘并提醒."""

    def test_due_memo_sends_notification_and_marks_sent(self, user):
        """到期未完成备忘 → 发通知 + reminder_sent=True + 返回 1"""
        memo = _make_memo(user, timezone.now() - timedelta(minutes=5))
        sent = send_due_memo_reminders()
        assert sent == 1
        memo.refresh_from_db()
        assert memo.reminder_sent is True
        notif = _task_notifs(user).first()
        assert notif is not None
        assert "备忘提醒" in notif.title

    def test_future_memo_not_sent(self, user):
        """未到提醒时间 → 不发送"""
        _make_memo(user, timezone.now() + timedelta(hours=1))
        assert send_due_memo_reminders() == 0
        assert Memo.objects.get(user=user).reminder_sent is False
        assert _task_notifs(user).count() == 0

    def test_completed_memo_not_sent(self, user):
        """已完成的备忘 → 不提醒"""
        _make_memo(user, timezone.now() - timedelta(minutes=5), is_completed=True)
        assert send_due_memo_reminders() == 0
        assert _task_notifs(user).count() == 0

    def test_no_reminder_time_not_sent(self, user):
        """reminder_time 为空 → 不提醒"""
        _make_memo(user, None)
        assert send_due_memo_reminders() == 0
        assert _task_notifs(user).count() == 0

    def test_already_sent_not_resent(self, user):
        """已提醒过的备忘 → 不重复发送(幂等)"""
        _make_memo(user, timezone.now() - timedelta(minutes=5), reminder_sent=True)
        assert send_due_memo_reminders() == 0
        assert _task_notifs(user).count() == 0

    def test_idempotent_across_runs(self, user):
        """重复执行任务 → 第二次不再发送(防轰炸)"""
        _make_memo(user, timezone.now() - timedelta(minutes=5))
        assert send_due_memo_reminders() == 1
        assert send_due_memo_reminders() == 0
        # 仅一条任务通知
        assert _task_notifs(user).count() == 1

    def test_multiple_memos_multiple_users(self, user, db):
        """多用户多备忘 → 各自收到提醒"""
        other = CustomUser.objects.create_user(username="memo_task_user_b", password="pass123")
        _make_memo(user, timezone.now() - timedelta(minutes=5), title="A")
        _make_memo(other, timezone.now() - timedelta(minutes=5), title="B")
        assert send_due_memo_reminders() == 2
        assert _task_notifs(user).count() == 1
        assert _task_notifs(other).count() == 1


class TestRescheduleResetsReminderSent:
    """改期到未来 → 重置 reminder_sent(P0-2 序列化器逻辑)."""

    def test_reschedule_to_future_resets_flag(self, user):
        from ..serializers import MemoSerializer

        memo = _make_memo(user, timezone.now() - timedelta(minutes=5), reminder_sent=True)
        new_time = timezone.now() + timedelta(days=1)
        serializer = MemoSerializer(memo, data={"reminder_time": new_time.isoformat()}, partial=True)
        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()
        assert updated.reminder_sent is False

    def test_reschedule_to_past_keeps_flag(self, user):
        """改到过去(reminder_sent=True)不重置,避免立即重发"""
        from ..serializers import MemoSerializer

        memo = _make_memo(user, timezone.now() - timedelta(minutes=5), reminder_sent=True)
        new_time = timezone.now() - timedelta(minutes=1)
        serializer = MemoSerializer(memo, data={"reminder_time": new_time.isoformat()}, partial=True)
        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()
        assert updated.reminder_sent is True


class TestMigrationBackfill:
    """迁移 0004 回填逻辑(评审 M-3):防首次部署对历史过期备忘补发提醒风暴."""

    def test_backfill_marks_expired_memos_sent(self, user):
        """存量已过期备忘被回填 reminder_sent=True,未到期的不受影响"""
        import importlib

        from django.apps import apps

        migration = importlib.import_module("memos.migrations.0004_memo_reminder_sent")

        expired = _make_memo(user, timezone.now() - timedelta(days=30), title="历史过期")
        future = _make_memo(user, timezone.now() + timedelta(days=1), title="未来")
        assert expired.reminder_sent is False
        assert future.reminder_sent is False

        migration.backfill_reminder_sent(apps, None)

        expired.refresh_from_db()
        future.refresh_from_db()
        assert expired.reminder_sent is True
        assert future.reminder_sent is False

    def test_backfill_idempotent(self, user):
        """重复执行回填无副作用"""
        import importlib

        from django.apps import apps

        migration = importlib.import_module("memos.migrations.0004_memo_reminder_sent")
        _make_memo(user, timezone.now() - timedelta(days=1))
        migration.backfill_reminder_sent(apps, None)
        migration.backfill_reminder_sent(apps, None)
        assert Memo.objects.filter(reminder_sent=True).count() == 1
