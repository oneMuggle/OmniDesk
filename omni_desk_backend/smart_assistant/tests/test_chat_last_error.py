"""P0-K chat last_error 持久化测试

编排层抛出未收口异常时:view 返回 500 + detail,并把错误写入
session.last_error(供前端展示与运维排查)。
"""
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from smart_assistant.models import SmartAssistantSession


@pytest.mark.django_db
class TestChatLastError:
    @patch("smart_assistant.views.chat_sync.AgentOrchestrator")
    def test_exception_persisted_to_session_last_error(self, mock_orch_cls, admin_user_obj):
        session = SmartAssistantSession.objects.create(
            user=admin_user_obj, title="历史会话", messages=[]
        )
        mock_orch_cls.return_value.process.side_effect = RuntimeError("boom")

        client = APIClient()
        client.force_authenticate(user=admin_user_obj)
        resp = client.post(
            "/api/smart-assistant/chat/",
            {"query": "你好", "conversation_id": session.id},
            format="json",
        )

        assert resp.status_code == 500
        assert resp.data["detail"] == "boom"
        session.refresh_from_db()
        assert session.last_error == "boom"

    @patch("smart_assistant.views.chat_sync.AgentOrchestrator")
    def test_exception_without_session_returns_500(self, mock_orch_cls, admin_user_obj):
        """无会话上下文时同样返回 500(无 session 可写,不崩溃)。"""
        mock_orch_cls.return_value.process.side_effect = RuntimeError("boom")

        client = APIClient()
        client.force_authenticate(user=admin_user_obj)
        resp = client.post("/api/smart-assistant/chat/", {"query": "你好"}, format="json")

        assert resp.status_code == 500
        assert resp.data["detail"] == "boom"
        assert not SmartAssistantSession.objects.exists()

    @patch("smart_assistant.views.chat_sync.AgentOrchestrator")
    def test_success_clears_path_without_error(self, mock_orch_cls, admin_user_obj):
        """成功路径不触发 last_error 逻辑。"""
        session = SmartAssistantSession.objects.create(
            user=admin_user_obj, title="历史会话", messages=[]
        )
        mock_orch_cls.return_value.process.return_value = {
            "answer": "回答",
            "intent": "general_chat",
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "usage": None,
        }

        client = APIClient()
        client.force_authenticate(user=admin_user_obj)
        resp = client.post(
            "/api/smart-assistant/chat/",
            {"query": "你好", "conversation_id": session.id},
            format="json",
        )

        assert resp.status_code == 200
        session.refresh_from_db()
        assert session.last_error == ""
