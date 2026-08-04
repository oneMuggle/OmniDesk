"""SmartChatViewSet.create confirm replay 路径单元测试(confirm-replay 框架 Phase C)。

覆盖:
- 带 confirm_token + 缓存命中 + 工具存在 → replay 成功,confirmed=True
- 带 confirm_token + 缓存未命中 → 410 Gone
- 带 confirm_token + 跨用户重放 → 403 Forbidden
- 带 confirm_token + 工具未注册 → 500
- replay 成功后 draft 被清理(防重放)
- 不带 confirm_token → 走既有 orchestrator 路径
"""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from smart_assistant.cache import set_confirmation_draft
from smart_assistant.models import SmartAssistantSession
from smart_assistant.tools.base import BaseTool


# ---------------------------------------------------------------------------
# Mock 工具
# ---------------------------------------------------------------------------


class _MockReplayTool(BaseTool):
    """replay 时真正执行的工具"""

    name = "mock_replay_tool"
    description = "mock 工具"
    intent_type = "mock_intent"
    risk_level = "write"
    require_confirmation = True

    def execute(self, query=None, context=None, **kwargs):
        # 检测 confirmed 模式
        if isinstance(context, dict) and context.get("confirmed"):
            return {"found": True, "result": "replayed_successfully", "summary": "操作已重放"}
        return {"found": True, "result": "not_replayed"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def mock_user(db):
    from users.models import CustomUser

    user = CustomUser.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
    return user


@pytest.fixture
def other_user(db):
    from users.models import CustomUser

    return CustomUser.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="testpass123",
    )


# ---------------------------------------------------------------------------
# 测试:replay 成功路径
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestReplaySuccess:
    """replay 成功路径。"""

    def test_valid_token_replay_success(self, api_client, mock_user):
        """有效 token + 缓存命中 + 工具存在 → replay 成功"""
        # 1. 存 draft
        token = "test-token-123"
        set_confirmation_draft(
            token,
            {
                "tool_name": "mock_replay_tool",
                "user_query": "original query",
                "context_sig": f"u{mock_user.pk}_sself",
                "draft": {"summary": "draft summary"},
            },
        )

        api_client.force_authenticate(user=mock_user)

        with patch(
            "smart_assistant.views.chat.ToolRegistry.get_tool",
            return_value=_MockReplayTool(),
        ):
            response = api_client.post(
                "/api/smart-assistant/chat/",
                {"query": "original query", "confirm_token": token},
                format="json",
            )

        assert response.status_code == 200
        data = response.json()
        assert data["confirmed"] is True
        assert data["error"] is False
        assert data["tool_used"] == "mock_replay_tool"
        assert data["tool_result"]["result"] == "replayed_successfully"

    def test_replay_success_clears_draft(self, api_client, mock_user):
        """replay 成功后 draft 被清理(防重放)"""
        from smart_assistant.cache import get_confirmation_draft

        token = "test-token-clear"
        set_confirmation_draft(
            token,
            {
                "tool_name": "mock_replay_tool",
                "user_query": "query",
                "context_sig": f"u{mock_user.pk}_sself",
                "draft": {},
            },
        )

        api_client.force_authenticate(user=mock_user)

        with patch(
            "smart_assistant.views.chat.ToolRegistry.get_tool",
            return_value=_MockReplayTool(),
        ):
            response = api_client.post(
                "/api/smart-assistant/chat/",
                {"query": "query", "confirm_token": token},
                format="json",
            )

        assert response.status_code == 200
        # draft 已被清理
        assert get_confirmation_draft(token) is None


# ---------------------------------------------------------------------------
# 测试:replay 失败路径
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestReplayFailure:
    """replay 失败路径。"""

    def test_expired_or_nonexistent_token_returns_410(self, api_client, mock_user):
        """无效/过期 token → 410 Gone"""
        api_client.force_authenticate(user=mock_user)

        response = api_client.post(
            "/api/smart-assistant/chat/",
            {"query": "test", "confirm_token": "nonexistent-token"},
            format="json",
        )

        assert response.status_code == 410
        data = response.json()
        assert data["code"] == "confirmation_expired"

    def test_cross_user_token_replay_returns_403(self, api_client, mock_user, other_user):
        """跨用户重放 → 403 Forbidden"""
        token = "test-token-cross"
        set_confirmation_draft(
            token,
            {
                "tool_name": "mock_replay_tool",
                "user_query": "query",
                "context_sig": f"u{other_user.pk}_sself",  # 属于 other_user
                "draft": {},
            },
        )

        # mock_user 尝试 replay other_user 的 token
        api_client.force_authenticate(user=mock_user)

        response = api_client.post(
            "/api/smart-assistant/chat/",
            {"query": "query", "confirm_token": token},
            format="json",
        )

        assert response.status_code == 403
        data = response.json()
        assert data["code"] == "confirmation_user_mismatch"

    def test_tool_not_registered_returns_500(self, api_client, mock_user):
        """draft 中的 tool_name 未注册 → 500"""
        token = "test-token-unregistered"
        set_confirmation_draft(
            token,
            {
                "tool_name": "nonexistent_tool",
                "user_query": "query",
                "context_sig": f"u{mock_user.pk}_sself",
                "draft": {},
            },
        )

        api_client.force_authenticate(user=mock_user)

        # ToolRegistry.get_tool 返回 None
        with patch(
            "smart_assistant.views.chat.ToolRegistry.get_tool",
            return_value=None,
        ):
            response = api_client.post(
                "/api/smart-assistant/chat/",
                {"query": "query", "confirm_token": token},
                format="json",
            )

        assert response.status_code == 500
        data = response.json()
        assert "未注册" in data["detail"]


# ---------------------------------------------------------------------------
# 测试:不带 confirm_token 走既有路径
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNoConfirmToken:
    """不带 confirm_token → 走既有 orchestrator 路径。"""

    def test_no_confirm_token_uses_orchestrator(self, api_client, mock_user):
        """不带 confirm_token → 走既有 orchestrator.process 路径"""
        api_client.force_authenticate(user=mock_user)

        with patch(
            "smart_assistant.views.chat.AgentOrchestrator"
        ) as MockOrchestrator:
            mock_instance = MockOrchestrator.return_value
            mock_instance.process.return_value = {
                "answer": "test answer",
                "intent": "test_intent",
                "tool_used": "test_tool",
                "tool_result": {},
                "sources": None,
                "error": False,
            }

            response = api_client.post(
                "/api/smart-assistant/chat/",
                {"query": "test query"},
                format="json",
            )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "test answer"
        assert data.get("confirmed") is not True  # 没有 confirmed 字段
        mock_instance.process.assert_called_once()
