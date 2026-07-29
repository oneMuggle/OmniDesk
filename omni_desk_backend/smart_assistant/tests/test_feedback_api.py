"""AgentLog 用户反馈 API 测试。

契约：PATCH /api/smart-assistant/agent-logs/{id}/feedback/
    请求体 {"feedback": "up" | "down" | null}
    - 200 → {"feedback": <写入值>}（清除时为 null）
    - 400 → 非法值或缺失 feedback 字段
    - 404 → 日志不存在，或日志不属于当前用户
"""

import pytest
from rest_framework import status

from smart_assistant.models import AgentLog, SmartAssistantSession
from users.models import CustomUser


def _create_log(user, **kwargs):
    """创建一条归属指定用户的 AgentLog（通过 session 关联）。"""
    session = SmartAssistantSession.objects.create(user=user, title="测试会话")
    defaults = {
        "session": session,
        "user_query": "明天谁值班？",
        "intent": "schedule_query",
        "tool_used": "schedule_query",
        "tool_input": {"query": "明天谁值班？"},
        "tool_output": {"found": True},
        "llm_response": "明天张三值班。",
    }
    defaults.update(kwargs)
    return AgentLog.objects.create(**defaults)


class TestFeedbackApi:
    """PATCH /api/smart-assistant/agent-logs/{id}/feedback/"""

    def test_feedback_up_writes_field(self, authenticated_client, admin_user_obj):
        """提交 up：200 返回 {"feedback": "up"}，落库 user_feedback="up"。"""
        log = _create_log(admin_user_obj)

        resp = authenticated_client.patch(
            f"/api/smart-assistant/agent-logs/{log.id}/feedback/",
            {"feedback": "up"},
            format="json",
        )

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == {"feedback": "up"}
        log.refresh_from_db()
        assert log.user_feedback == "up"

    def test_feedback_down_writes_field(self, authenticated_client, admin_user_obj):
        """提交 down：200 返回 {"feedback": "down"}，落库 user_feedback="down"。"""
        log = _create_log(admin_user_obj)

        resp = authenticated_client.patch(
            f"/api/smart-assistant/agent-logs/{log.id}/feedback/",
            {"feedback": "down"},
            format="json",
        )

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == {"feedback": "down"}
        log.refresh_from_db()
        assert log.user_feedback == "down"

    def test_feedback_change_up_to_down(self, authenticated_client, admin_user_obj):
        """改选：先 up 后 down，最终值为 down（覆盖写入）。"""
        log = _create_log(admin_user_obj)
        url = f"/api/smart-assistant/agent-logs/{log.id}/feedback/"

        resp_up = authenticated_client.patch(url, {"feedback": "up"}, format="json")
        assert resp_up.status_code == status.HTTP_200_OK

        resp_down = authenticated_client.patch(url, {"feedback": "down"}, format="json")
        assert resp_down.status_code == status.HTTP_200_OK
        assert resp_down.data == {"feedback": "down"}

        log.refresh_from_db()
        assert log.user_feedback == "down"

    def test_feedback_null_clears(self, authenticated_client, admin_user_obj):
        """清除：传 null → 200 返回 {"feedback": null}，落库为空字符串。"""
        log = _create_log(admin_user_obj, user_feedback="up")
        url = f"/api/smart-assistant/agent-logs/{log.id}/feedback/"

        resp = authenticated_client.patch(url, {"feedback": None}, format="json")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data == {"feedback": None}
        log.refresh_from_db()
        assert log.user_feedback == ""

    def test_feedback_invalid_value_returns_400(self, authenticated_client, admin_user_obj):
        """非法值（非 up/down）→ 400，且不改库。"""
        log = _create_log(admin_user_obj, user_feedback="up")

        resp = authenticated_client.patch(
            f"/api/smart-assistant/agent-logs/{log.id}/feedback/",
            {"feedback": "sideways"},
            format="json",
        )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        log.refresh_from_db()
        assert log.user_feedback == "up"

    def test_feedback_missing_field_returns_400(self, authenticated_client, admin_user_obj):
        """缺失 feedback 字段 → 400。"""
        log = _create_log(admin_user_obj)

        resp = authenticated_client.patch(
            f"/api/smart-assistant/agent-logs/{log.id}/feedback/",
            {},
            format="json",
        )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_feedback_other_users_log_returns_404(self, authenticated_client, admin_user_obj):
        """他人日志 → 404（日志通过 session 归属另一用户）。"""
        other_user = CustomUser.objects.create_user(
            username="other_feedback_user", password="other123"
        )
        log = _create_log(other_user)

        resp = authenticated_client.patch(
            f"/api/smart-assistant/agent-logs/{log.id}/feedback/",
            {"feedback": "up"},
            format="json",
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        log.refresh_from_db()
        assert log.user_feedback == ""

    def test_feedback_unauthenticated_returns_401(self, api_client, admin_user_obj):
        """未认证 → 401。"""
        log = _create_log(admin_user_obj)

        resp = api_client.patch(
            f"/api/smart-assistant/agent-logs/{log.id}/feedback/",
            {"feedback": "up"},
            format="json",
        )

        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
