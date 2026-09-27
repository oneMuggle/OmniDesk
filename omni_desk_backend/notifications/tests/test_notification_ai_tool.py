"""AI 工具 notification_query：只能查本人通知，任何 scope 都不扩大。"""

import pytest
from django.contrib.auth import get_user_model

from notifications.ai_tools import NotificationQueryTool
from notifications.models import Notification
from smart_assistant.scope import SmartAssistantScope
from smart_assistant.tools.tool_context import ToolContext

User = get_user_model()


def _notify(user, title, *, type_="system", is_read=False, content="内容"):
    return Notification.objects.create(user=user, type=type_, title=title, content=content, is_read=is_read)


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="notif_ai_alice", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="notif_ai_bob", password="x")


@pytest.mark.django_db
class TestNotificationQueryTool:
    def test_only_own_notifications_even_for_global_scope(self, alice, bob):
        _notify(alice, "Alice 的通知")
        _notify(bob, "Bob 的通知")
        admin = User.objects.create_superuser(username="notif_ai_admin", password="x")
        _notify(admin, "管理员的通知")

        result = NotificationQueryTool().execute(
            context=ToolContext(user=admin, scope=SmartAssistantScope.GLOBAL), params={"query": "通知"}
        )
        assert [n["title"] for n in result["notifications"]] == ["管理员的通知"]

        result = NotificationQueryTool().execute(context=ToolContext(user=alice), params={"query": "通知"})
        assert [n["title"] for n in result["notifications"]] == ["Alice 的通知"]

    def test_unread_count_and_filters(self, alice):
        _notify(alice, "已读的排班变更", type_="schedule_change", is_read=True)
        _notify(alice, "未读的排班变更", type_="schedule_change")
        _notify(alice, "未读的系统消息", type_="system", content="系统升级")

        tool = NotificationQueryTool()
        ctx = ToolContext(user=alice)

        all_items = tool.execute(context=ctx, params={"query": "最近通知"})
        assert all_items["found"] is True
        assert all_items["unread_count"] == 2
        assert all_items["count"] == 3

        unread = tool.execute(context=ctx, params={"query": "看看通知", "unread_only": True})
        assert {n["title"] for n in unread["notifications"]} == {"未读的排班变更", "未读的系统消息"}

        by_type = tool.execute(context=ctx, params={"query": "排班通知", "type": "schedule_change"})
        assert {n["title"] for n in by_type["notifications"]} == {"已读的排班变更", "未读的排班变更"}

        by_keyword = tool.execute(context=ctx, params={"query": "升级", "keyword": "升级"})
        assert [n["title"] for n in by_keyword["notifications"]] == ["未读的系统消息"]

        limited = tool.execute(context=ctx, params={"query": "通知", "limit": 1})
        assert limited["count"] == 1

    def test_legacy_query_detects_unread(self, alice):
        _notify(alice, "已读", is_read=True)
        _notify(alice, "未读")
        result = NotificationQueryTool().execute("我有哪些未读通知", {"user": alice})
        assert [n["title"] for n in result["notifications"]] == ["未读"]

    def test_empty_and_anonymous(self, alice):
        empty = NotificationQueryTool().execute(context=ToolContext(user=alice), params={"query": "未读通知"})
        assert empty["found"] is False
        assert empty["unread_count"] == 0
        assert "未读通知" in empty["message"]

        anonymous = NotificationQueryTool().execute("通知", {"user": None})
        assert anonymous["found"] is False
        assert "notifications" not in anonymous
