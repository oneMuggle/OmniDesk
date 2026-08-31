"""confirm-replay 框架端到端测试(confirm-replay 框架 Phase D)。

覆盖完整链路:
- 用户首次请求 → orchestrator 拦截 → 返回 awaiting_confirmation + confirmation_token
- 用户带 token 二次请求 → 视图层 replay → 返回最终结果
- 用户取消(token 过期或无效) → 410
- 跨用户重放 → 403
"""

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from smart_assistant.hooks.base import HookEvent, get_registry
from smart_assistant.tools.base import BaseTool


# ---------------------------------------------------------------------------
# Mock 工具
# ---------------------------------------------------------------------------


class _E2EWriteTool(BaseTool):
    """端到端测试用的 write 工具,支持 dry_run + confirmed 两种模式"""

    name = "e2e_write_tool"
    description = "端到端测试工具"
    intent_type = "e2e_intent"
    risk_level = "write"
    require_confirmation = True

    def execute(self, query=None, context=None, **kwargs):
        ctx = context if isinstance(context, dict) else {}

        # dry_run 模式:返回 draft(不真正执行)
        if ctx.get("dry_run"):
            return {
                "found": True,
                "draft": {
                    "summary": f"将为以下操作发起确认: {query}",
                    "fields": {
                        "operation_id": "op-e2e",
                        "operation": "e2e_write_tool",
                        "phase": "dry_run",
                        "scope": "self",
                        "status": "awaiting_confirmation",
                        "count": 1,
                        "total": 1,
                        "content": "CONTENT_SECRET_123",
                        "recipient_ids": ["RECIPIENT_ID_SECRET_123"],
                        "recipient_names": ["RECIPIENT_NAME_SECRET_123"],
                        "credentials": "CREDENTIAL_SECRET_123",
                        "query": query,
                    },
                },
            }

        # confirmed 模式:真正执行
        if ctx.get("confirmed"):
            return {
                "found": True,
                "result": "e2e_executed",
                "summary": f"操作已完成: {query}",
            }

        # 兜底(不应该走到这里,因为 orchestrator 会拦截)
        return {"found": True, "result": "unexpected_direct_execution"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """每个测试前清空全局注册表"""
    get_registry(reset=True)
    yield
    get_registry(reset=True)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_a(db):
    from users.models import CustomUser

    return CustomUser.objects.create_user(
        username="user_a",
        email="a@example.com",
        password="testpass123",
    )


@pytest.fixture
def user_b(db):
    from users.models import CustomUser

    return CustomUser.objects.create_user(
        username="user_b",
        email="b@example.com",
        password="testpass123",
    )


# ---------------------------------------------------------------------------
# Helper:注册一个 pre hook 返回 Reject(confirmation_required)
# ---------------------------------------------------------------------------


def _register_confirm_guard():
    """注册生产真实 ConfirmationHook(替代内联 ConfirmGuardHook)。"""
    from smart_assistant.hooks.builtin.confirmation import ConfirmationHook

    registry = get_registry()
    registry.register(HookEvent.PRE_EXECUTE, ConfirmationHook(), priority=20)


# ---------------------------------------------------------------------------
# 端到端测试
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConfirmReplayE2E:
    """完整链路端到端。"""

    @patch("smart_assistant.agent.orchestrator.classify_intent", return_value="e2e_intent")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan", return_value=[])
    def test_full_replay_chain(self, mock_chain_plan, mock_classify, api_client, user_a):
        """完整链路:首次请求 → awaiting_confirmation → 二次请求 → 最终结果"""
        _register_confirm_guard()
        api_client.force_authenticate(user=user_a)

        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_E2EWriteTool(),
        ), patch(
            "smart_assistant.views.chat_sync.ToolRegistry.get_tool_for_user",
            return_value=_E2EWriteTool(),
        ):
            # Step 1: 首次请求 → awaiting_confirmation
            response_1 = api_client.post(
                "/api/smart-assistant/chat/",
                {"query": "QUERY_SECRET_123"},
                format="json",
            )

            assert response_1.status_code == 200
            data_1 = response_1.json()
            assert data_1["awaiting_confirmation"] is True
            assert data_1["confirmation_token"]  # 非空
            assert data_1["tool_used"] == "e2e_write_tool"
            assert set(data_1["tool_result"]) == {"draft"}
            public_draft = data_1["tool_result"]["draft"]
            assert public_draft["summary"]
            assert isinstance(public_draft["fields"], dict)
            allowed_public_field_keys = {
                "operation_id",
                "operation",
                "phase",
                "scope",
                "status",
                "count",
                "total",
            }
            assert set(public_draft["fields"]) <= allowed_public_field_keys
            for sensitive_key in (
                "content",
                "recipient_ids",
                "recipient_names",
                "credentials",
                "query",
            ):
                assert sensitive_key not in public_draft["fields"]
            public_draft_json = str(data_1["tool_result"])
            for sentinel in (
                "CONTENT_SECRET_123",
                "RECIPIENT_ID_SECRET_123",
                "RECIPIENT_NAME_SECRET_123",
                "CREDENTIAL_SECRET_123",
                "QUERY_SECRET_123",
            ):
                assert sentinel not in public_draft_json
            assert data_1["error"] is False

            token = data_1["confirmation_token"]

            # Step 2: 二次请求 → replay → 最终结果
            response_2 = api_client.post(
                "/api/smart-assistant/chat/",
                {"query": "QUERY_SECRET_123", "confirm_token": token},
                format="json",
            )

            assert response_2.status_code == 200
            data_2 = response_2.json()
            assert data_2["confirmed"] is True
            assert data_2["error"] is False
            assert data_2["tool_used"] == "e2e_write_tool"
            assert data_2["tool_result"]["found"] is True
            assert data_2["tool_result"]["summary"] == "操作已完成: QUERY_SECRET_123"
            assert set(data_2["tool_result"]) == {"found", "summary"}
            assert data_2["answer"].startswith("操作已完成")

    @patch("smart_assistant.agent.orchestrator.classify_intent", return_value="e2e_intent")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan", return_value=[])
    def test_cancel_via_invalid_token(self, mock_chain_plan, mock_classify, api_client, user_a):
        """用户取消:用无效 token 二次请求 → 410"""
        _register_confirm_guard()
        api_client.force_authenticate(user=user_a)

        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_E2EWriteTool(),
        ):
            # 首次请求 → 拿到 token
            response_1 = api_client.post(
                "/api/smart-assistant/chat/",
                {"query": "测试取消"},
                format="json",
            )

            token = response_1.json()["confirmation_token"]

            # 模拟 token 过期:直接清理
            from smart_assistant.cache import clear_confirmation_draft

            clear_confirmation_draft(token)

            # 二次请求 → 410
            response_2 = api_client.post(
                "/api/smart-assistant/chat/",
                {"query": "测试取消", "confirm_token": token},
                format="json",
            )

            assert response_2.status_code == 410
            assert response_2.json()["code"] == "confirmation_expired"

    @patch("smart_assistant.agent.orchestrator.classify_intent", return_value="e2e_intent")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan", return_value=[])
    def test_cross_user_replay_forbidden(self, mock_chain_plan, mock_classify, api_client, user_a, user_b):
        """跨用户重放 → 403"""
        _register_confirm_guard()

        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_E2EWriteTool(),
        ):
            # user_a 首次请求 → 拿到 token
            api_client.force_authenticate(user=user_a)
            response_1 = api_client.post(
                "/api/smart-assistant/chat/",
                {"query": "跨用户测试"},
                format="json",
            )

            token = response_1.json()["confirmation_token"]

            # user_b 尝试 replay user_a 的 token → 403
            api_client.force_authenticate(user=user_b)
            response_2 = api_client.post(
                "/api/smart-assistant/chat/",
                {"query": "跨用户测试", "confirm_token": token},
                format="json",
            )

            assert response_2.status_code == 403
            assert response_2.json()["code"] == "confirmation_user_mismatch"
