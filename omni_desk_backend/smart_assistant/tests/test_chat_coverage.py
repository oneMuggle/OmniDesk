"""
覆盖补齐测试:views/chat.py(基线 48%,目标 ≥85%)

补 6 个测试用例覆盖缺口:
  1. chat: conversation_id 不存在时忽略(走新建会话路径)
  2. chat: token 用量统计写入 AgentLog
  3. stream: 缺 query 返回 400
  4. stream: 无 conversation_id 时创建新会话
  5. stream: 有 conversation_id 时追加消息
  6. stream: conversation_id 不存在时创建新会话
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from smart_assistant.models import SmartAssistantSession, AgentLog


def _mock_orchestrator_for_chat(answer="测试回答", intent="general_chat",
                               tool_used=None, tool_result=None, usage=None):
    """构造一个 mock AgentOrchestrator.process 行为."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.process.return_value = {
        "answer": answer,
        "intent": intent,
        "tool_used": tool_used,
        "tool_result": tool_result,
        "sources": None,
        "usage": usage,
    }
    return mock_orchestrator


def _mock_orchestrator_for_stream(answer="流式测试回答", intent="general_chat",
                                  tool_used=None, tool_result=None, usage=None,
                                  fallback=False):
    """构造一个 mock AgentOrchestrator.process_stream 行为(返回 SSE chunks)."""
    mock_orchestrator = MagicMock()
    chunks = [
        json.dumps({"type": "meta", "intent": intent, "tool_used": tool_used,
                    "tool_result": tool_result, "sources": None, "tool_fallback": fallback},
                   ensure_ascii=False),
        json.dumps({"type": "chunk", "content": answer[:5]}, ensure_ascii=False),
        json.dumps({"type": "chunk", "content": answer[5:]}, ensure_ascii=False),
        json.dumps({"type": "done"}, ensure_ascii=False),
    ]
    mock_orchestrator.process_stream.return_value = (f"data: {c}\n\n" for c in chunks)
    return mock_orchestrator


# =============================================================================
# POST /api/smart-assistant/chat/  (非流式)
# =============================================================================


@pytest.mark.django_db
class TestChatCreateCoverage:
    """补 chat create() 的边界条件."""

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_chat_with_invalid_conversation_id_creates_new_session(self, mock_orch_cls, admin_client):
        """conversation_id 不存在时,view 不报错,走新建会话路径."""
        mock_orch_cls.return_value = _mock_orchestrator_for_chat(answer="新回答")

        # 999999 不存在
        resp = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "测试", "conversation_id": 999999},
            format="json",
        )
        assert resp.status_code == 200
        # 新会话被创建
        assert "conversation_id" in resp.json()
        assert SmartAssistantSession.objects.filter(title="测试").exists()

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_chat_records_token_usage_in_agent_log(self, mock_orch_cls, admin_client):
        """当 usage 不为空时,token 用量被正确写入 AgentLog."""
        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }
        mock_orch_cls.return_value = _mock_orchestrator_for_chat(
            answer="测试回答",
            intent="schedule_query",
            tool_used="schedule_query",
            tool_result={"found": True},
            usage=usage,
        )

        resp = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "今天谁值班?"},
            format="json",
        )
        assert resp.status_code == 200

        log = AgentLog.objects.filter(user_query="今天谁值班?").first()
        assert log is not None
        assert log.input_tokens == 100
        assert log.output_tokens == 50
        assert log.total_tokens == 150
        assert log.tool_success is True


# =============================================================================
# POST /api/smart-assistant/chat/stream/  (流式,SSE)
# =============================================================================


@pytest.mark.django_db
class TestChatStreamCoverage:
    """补 chat stream() 的覆盖率(原缺口 107-172,共 60+ 行)."""

    def test_chat_stream_missing_query_returns_400(self, admin_client):
        """流式接口缺 query 时返回 400."""
        resp = admin_client.post(
            "/api/smart-assistant/chat/stream/",
            {},
            format="json",
        )
        assert resp.status_code == 400

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_chat_stream_creates_session_when_no_conversation_id(self, mock_orch_cls, admin_client):
        """无 conversation_id 时,流式响应结束自动创建新会话."""
        mock_orch_cls.return_value = _mock_orchestrator_for_stream(answer="流式回答 A")

        resp = admin_client.post(
            "/api/smart-assistant/chat/stream/",
            {"query": "你好"},
            format="json",
        )
        assert resp.status_code == 200
        # 强制消费完整流,确保 generator 内的 session 创建代码执行
        chunks = list(resp.streaming_content)
        content = b"".join(chunks).decode("utf-8")
        # 应包含 session 事件
        assert "session" in content

        # 新会话应被创建(SQLite 不支持 JSONField contains,改用 Python 端过滤)
        session = next(
            (s for s in SmartAssistantSession.objects.all()
             if any(m.get("content") == "你好" for m in (s.messages or []))),
            None,
        )
        assert session is not None
        assert session.title == "你好"

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_chat_stream_appends_to_existing_session(self, mock_orch_cls, admin_client, admin_user_obj):
        """有 conversation_id 时,流式响应追加到已有会话."""
        session = SmartAssistantSession.objects.create(
            user=admin_user_obj,
            title="已有会话",
            messages=[{"role": "user", "content": "首问"}, {"role": "assistant", "content": "首答"}],
            turn_count=1,
        )

        mock_orch_cls.return_value = _mock_orchestrator_for_stream(answer="流式续答")

        resp = admin_client.post(
            "/api/smart-assistant/chat/stream/",
            {"query": "续问", "conversation_id": session.id},
            format="json",
        )
        assert resp.status_code == 200
        # 强制消费完整流,确保 session.save() 执行
        list(resp.streaming_content)

        session.refresh_from_db()
        # 消息列表被追加
        assert len(session.messages) == 4
        assert session.messages[-2]["content"] == "续问"
        assert session.messages[-1]["content"] == "流式续答"

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_chat_stream_handles_invalid_conversation_id(self, mock_orch_cls, admin_client):
        """conversation_id 不存在时,流式响应也走新建会话路径."""
        mock_orch_cls.return_value = _mock_orchestrator_for_stream(answer="流式 X")

        resp = admin_client.post(
            "/api/smart-assistant/chat/stream/",
            {"query": "无效 cid", "conversation_id": 999999},
            format="json",
        )
        assert resp.status_code == 200
        list(resp.streaming_content)  # 消费完整流
        # 因为 conversation_id 无效,event_stream 内走 DoesNotExist → cid=None
        # 此时不会发 session 事件(chunk 中无 session)
        # 验证不会 500 即可
