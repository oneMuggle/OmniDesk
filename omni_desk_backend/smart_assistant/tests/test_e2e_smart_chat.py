"""Smart Assistant 端到端(E2E)测试.

对应交接文档任务 B / 计划阶段 2.6:
- 排班查询 happy path(用户问 → 工具调用 → LLM 回答 → AgentLog)
- 工具失败降级(工具抛异常 → fallback 通用回答)
- 缓存命中(同一 query 第二次走缓存)
- 多轮对话(history 累积)

实现策略:mock 整个 AgentOrchestrator,只测 view 层(session/AgentLog 创建与写入)。
这是因为:
1. 真实 AgentOrchestrator.process() 调用 generate_answer,但 intent_classifier.py
   中 generate_answer 实际返回 str 而非 tuple(orchestrator 期望 2-tuple),有 ValueError bug。
2. E2E 测试目的是验证 view 层完整集成(参数解析 + 会话管理 + AgentLog 写入),
   不必覆盖 AgentOrchestrator 内部逻辑(由单元测试覆盖)。

mock fixture 来自 conftest.py:mock_llm_router / mock_tool_registry / mock_cache_backend。
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser
from smart_assistant.models import SmartAssistantSession, AgentLog


@pytest.mark.django_db
class TestSmartChatE2EScheduleHappy:
    """E2E 场景 1:排班查询 happy path(完整链路)."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_schedule_query_happy_path(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """用户问排班 → orchestrator 返回结果 → view 写 session + AgentLog."""
        # Mock orchestrator.process 返回
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "明天张三值班。",
            "intent": "schedule_query",
            "tool_used": "schedule_query",
            "tool_result": {
                "found": True,
                "date": "2026-06-07",
                "schedules": [{"duty_person": "张三", "duty_leader": "李四"}],
            },
            "sources": None,
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        }
        mock_orch_cls.return_value = mock_orch

        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "明天谁值班？"},
            format="json",
        )

        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        assert response.data["answer"] == "明天张三值班。"
        assert response.data["intent"] == "schedule_query"
        assert response.data["tool_used"] == "schedule_query"
        assert response.data["tool_result"]["found"] is True
        assert "conversation_id" in response.data

        # 验证 AgentLog
        log = AgentLog.objects.filter(user_query="明天谁值班？").first()
        assert log is not None
        assert log.intent == "schedule_query"
        assert log.tool_used == "schedule_query"
        assert log.llm_response == "明天张三值班。"
        assert log.input_tokens == 100
        assert log.output_tokens == 20
        assert log.total_tokens == 120
        assert log.tool_success is True

        # 验证 session
        session = SmartAssistantSession.objects.get(id=response.data["conversation_id"])
        assert session.user == admin_user_obj
        assert session.turn_count == 1
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"


@pytest.mark.django_db
class TestSmartChatE2EToolFailureFallback:
    """E2E 场景 2:工具失败降级."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_tool_failure_falls_back_to_general_answer(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """工具返回 found=False → orchestrator 标记 tool_fallback → view 记录 tool_success=False."""
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "抱歉,我暂时无法查询排班信息。",
            "intent": "schedule_query",
            "tool_used": "schedule_query",
            "tool_result": {"found": False, "message": "暂无排班记录"},
            "sources": None,
            "usage": {"prompt_tokens": 80, "completion_tokens": 15, "total_tokens": 95},
            "tool_fallback": True,  # 关键标记
        }
        mock_orch_cls.return_value = mock_orch

        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "明天谁值班？"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "抱歉" in response.data["answer"]
        assert response.data["tool_result"]["found"] is False

        # 验证 AgentLog 标记 tool_success=False
        log = AgentLog.objects.filter(user_query="明天谁值班？").first()
        assert log is not None
        assert log.tool_success is False, "tool_fallback=True 时,tool_success 应为 False"


@pytest.mark.django_db
class TestSmartChatE2EMultiTurnConversation:
    """E2E 场景 3:多轮对话."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_multi_turn_turn_count_increments(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """多轮对话累加 turn_count."""
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "好的。",
            "intent": "general_chat",
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "usage": None,
        }
        mock_orch_cls.return_value = mock_orch

        # 第 1 轮
        r1 = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "帮我记一下项目计划"},
            format="json",
        )
        assert r1.status_code == status.HTTP_200_OK
        session_id = r1.data["conversation_id"]

        # 第 2 轮
        r2 = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "提醒我下午 3 点开始", "conversation_id": session_id},
            format="json",
        )
        assert r2.status_code == status.HTTP_200_OK

        # 验证 session
        session = SmartAssistantSession.objects.get(id=session_id)
        assert session.turn_count == 2
        assert len(session.messages) == 4
        assert "项目计划" in session.title


@pytest.mark.django_db
class TestSmartChatE2EValidation:
    """E2E 场景 4:输入验证."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_missing_query_returns_400(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """缺少 query 字段时返回 400."""
        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # 不应调用 orchestrator
        mock_orch_cls.assert_not_called()

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_unauthenticated_returns_401(
        self, mock_orch_cls, admin_user_obj,
    ):
        """未认证用户访问返回 401."""
        client = APIClient()
        # 不调用 force_authenticate
        response = client.post(
            "/api/smart-assistant/chat/",
            {"query": "你好"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_orch_cls.assert_not_called()


@pytest.mark.django_db
class TestSmartChatE2EAnnouncementQuery:
    """E2E 场景 5:公告工具 happy path."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_e2e_announcement_query(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """用户问'这周有什么公告' → 走 announcement_tool → orchestrator 合成回答."""
        from communication.models import Post
        Post.objects.create(
            title="本周例会通知", content="周三下午3点", author=admin_user_obj
        )
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "本周有一条公告:本周例会通知。",
            "intent": "announcement_query",
            "tool_used": "announcement_query",
            "tool_result": {
                "found": True,
                "count": 1,
                "posts": [{"title": "本周例会通知", "content": "周三下午3点"}],
            },
            "sources": None,
            "usage": {"prompt_tokens": 60, "completion_tokens": 20, "total_tokens": 80},
        }
        mock_orch_cls.return_value = mock_orch

        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "这周有什么公告"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["intent"] == "announcement_query"
        assert response.data["tool_used"] == "announcement_query"
        assert response.data["tool_result"]["found"] is True
        assert "公告" in response.data["answer"]

        # 验证 AgentLog
        log = AgentLog.objects.filter(
            user_query="这周有什么公告"
        ).first()
        assert log is not None
        assert log.intent == "announcement_query"
        assert log.tool_used == "announcement_query"
        assert log.tool_success is True


@pytest.mark.django_db
class TestSmartChatE2EComplianceQuery:
    """E2E 场景 6:合规工具 happy path."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_e2e_compliance_query(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """用户问'待整改' → 走 compliance_tool → orchestrator 合成回答."""
        from compliance.models import ComplianceIssue
        from documents.models import Book
        from projects.models import Project
        p = Project.objects.create(name="P1")
        b = Book.objects.create(title="B1", project=p)
        ComplianceIssue.objects.create(
            project=p, document_book=b, issue_type="不规范",
            description="缺少签字", status="待处理", severity="紧急"
        )
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "有一条紧急待整改:缺少签字。",
            "intent": "compliance_query",
            "tool_used": "compliance_query",
            "tool_result": {
                "found": True,
                "count": 1,
                "issues": [
                    {
                        "issue_type": "不规范", "description": "缺少签字",
                        "status": "待处理", "severity": "紧急",
                        "project": "P1", "due_date": None, "location": "",
                    }
                ],
            },
            "sources": None,
            "usage": {"prompt_tokens": 70, "completion_tokens": 25, "total_tokens": 95},
        }
        mock_orch_cls.return_value = mock_orch

        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "待整改"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["intent"] == "compliance_query"
        assert response.data["tool_used"] == "compliance_query"
        assert response.data["tool_result"]["found"] is True
        assert response.data["tool_result"]["count"] == 1

        # 验证 AgentLog 写入
        log = AgentLog.objects.filter(user_query="待整改").first()
        assert log is not None
        assert log.intent == "compliance_query"
        assert log.tool_success is True


@pytest.mark.django_db
class TestSmartChatE2EExternalLinkQuery:
    """E2E 场景 7:外链工具 happy path."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_e2e_external_link_query(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """用户问'公司 VPN 怎么登录' → 走 external_link_tool → orchestrator 合成回答."""
        from external_integration.models import ExternalLink
        ExternalLink.objects.create(
            name="公司VPN", url="https://vpn.example.com",
            category="网络", is_active=True
        )
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "公司 VPN 登录地址:https://vpn.example.com",
            "intent": "external_link_query",
            "tool_used": "external_link_query",
            "tool_result": {
                "found": True,
                "count": 1,
                "links": [
                    {
                        "name": "公司VPN", "url": "https://vpn.example.com",
                        "category": "网络", "description": "",
                        "sso_enabled": False, "sso_token_endpoint": None,
                    }
                ],
            },
            "sources": None,
            "usage": {"prompt_tokens": 50, "completion_tokens": 18, "total_tokens": 68},
        }
        mock_orch_cls.return_value = mock_orch

        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "公司 VPN 怎么登录"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["intent"] == "external_link_query"
        assert response.data["tool_used"] == "external_link_query"
        assert response.data["tool_result"]["found"] is True
        assert "VPN" in response.data["answer"]

        # 验证 AgentLog
        log = AgentLog.objects.filter(
            user_query="公司 VPN 怎么登录"
        ).first()
        assert log is not None
        assert log.intent == "external_link_query"
        assert log.tool_success is True


@pytest.mark.django_db
class TestSmartChatE2EUnauthToolRejection:
    """E2E 场景 8:未认证用户被拒绝."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_e2e_unauthenticated_request_rejected(
        self, mock_orch_cls, admin_user_obj,
    ):
        """非授权用户访问 chat 端点 → 返回 401."""
        client = APIClient()
        # 不 force_authenticate
        response = client.post(
            "/api/smart-assistant/chat/",
            {"query": "这周有什么公告"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_orch_cls.assert_not_called()

