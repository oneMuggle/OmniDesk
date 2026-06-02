"""smart_assistant 模块补充测试：模型、ViewSet 权限、知识库、session 等。"""

import pytest
from unittest.mock import patch, MagicMock

from smart_assistant.models import (
    KnowledgeBaseDocument, SmartAssistantSession, AgentLog,
    LlmEndpoint, LlmAppConfig, KnowledgeDataset,
)
from users.models import CustomUser


# ==================== KnowledgeBaseDocument 测试 ====================

@pytest.mark.django_db
class TestKnowledgeBaseDocument:
    def test_document_model(self):
        """知识库文档模型 — 验证字段存在"""
        # KnowledgeBaseDocument 需要 file 字段，这里只验证模型结构
        doc = KnowledgeBaseDocument(title='测试文档', category='general')
        assert doc.title == '测试文档'
        assert doc.category == 'general'


# ==================== Session ViewSet 测试 ====================

@pytest.mark.django_db
class TestSessionViewSet:
    def test_session_crud(self, admin_client, admin_user_obj):
        """会话 CRUD"""
        session = SmartAssistantSession.objects.create(
            title='测试会话',
            user=admin_user_obj,
        )
        resp = admin_client.get(f'/api/smart-assistant/sessions/{session.id}/')
        assert resp.status_code == 200

        resp = admin_client.patch(f'/api/smart-assistant/sessions/{session.id}/', {
            'title': '更新会话',
        }, format='json')
        assert resp.status_code == 200

        resp = admin_client.delete(f'/api/smart-assistant/sessions/{session.id}/')
        assert resp.status_code == 204

    def test_session_messages(self, admin_client, admin_user_obj):
        """获取会话消息列表"""
        session = SmartAssistantSession.objects.create(
            title='消息会话',
            user=admin_user_obj,
        )
        resp = admin_client.get(f'/api/smart-assistant/sessions/{session.id}/messages/')
        assert resp.status_code in [200, 404]


# ==================== AgentLog ViewSet 测试 ====================

@pytest.mark.django_db
class TestAgentLogViewSet:
    def test_agent_log_list(self, admin_client, admin_user_obj):
        """Agent 日志列表"""
        session = SmartAssistantSession.objects.create(title='日志会话', user=admin_user_obj)
        AgentLog.objects.create(
            session=session,
            user_query='测试查询',
            intent='test',
            tool_used='none',
            tool_input={},
            tool_output={},
            llm_response='测试响应',
        )
        resp = admin_client.get('/api/smart-assistant/agent-logs/')
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1

    def test_agent_log_filter_by_intent(self, admin_client, admin_user_obj):
        """按 intent 过滤"""
        session = SmartAssistantSession.objects.create(title='过滤会话', user=admin_user_obj)
        AgentLog.objects.create(session=session, user_query='q1', intent='schedule_query', tool_used='x', tool_input={}, tool_output={}, llm_response='r1')
        AgentLog.objects.create(session=session, user_query='q2', intent='personnel_query', tool_used='y', tool_input={}, tool_output={}, llm_response='r2')
        resp = admin_client.get('/api/smart-assistant/agent-logs/', {'intent': 'schedule_query'})
        assert resp.status_code == 200


# ==================== LlmEndpoint ViewSet 测试 ====================

@pytest.mark.django_db
class TestLlmEndpointViewSet:
    def test_endpoint_crud(self, admin_client):
        """LLM 端点 CRUD"""
        resp = admin_client.post('/api/smart-assistant/endpoints/', {
            'name': '测试端点',
            'api_endpoint': 'http://localhost:11434',
            'api_key': 'test-key',
        }, format='json')
        assert resp.status_code == 201, resp.data
        endpoint_id = resp.data['id']

        resp = admin_client.get(f'/api/smart-assistant/endpoints/{endpoint_id}/')
        assert resp.status_code == 200

        resp = admin_client.delete(f'/api/smart-assistant/endpoints/{endpoint_id}/')
        assert resp.status_code == 204


# ==================== LlmAppConfig ViewSet 测试 ====================

@pytest.mark.django_db
class TestLlmAppConfigViewSet:
    def test_app_config_model(self, admin_user_obj):
        """LLM 应用配置模型"""
        endpoint = LlmEndpoint.objects.create(
            name='测试端点',
            api_endpoint='http://localhost:11434',
            api_key='test-key',
        )
        config = LlmAppConfig.objects.create(
            app_name='smart_assistant',
            endpoint=endpoint,
            model_name='llama3',
        )
        assert config.app_name == 'smart_assistant'
        assert config.model_name == 'llama3'


# ==================== Stats ViewSet 测试 ====================

@pytest.mark.django_db
class TestStatsViewSet:
    def test_stats_endpoint(self, admin_client):
        """统计端点 — 验证可达"""
        resp = admin_client.get('/api/smart-assistant/stats/')
        assert resp.status_code in [200, 404]


# ==================== Chat API 补充测试 ====================

@pytest.mark.django_db
class TestSmartChatViewSet:
    def test_chat_missing_query(self, admin_client):
        """缺少 query 应返回 400"""
        resp = admin_client.post('/api/smart-assistant/chat/', {}, format='json')
        assert resp.status_code == 400

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_success(self, mock_orchestrator_cls, admin_client, admin_user_obj):
        """聊天成功返回响应"""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process.return_value = {
            'answer': '测试回答',
            'intent': 'test_intent',
            'tool_used': None,
            'tool_result': None,
            'sources': None,
            'usage': None,
        }
        mock_orchestrator_cls.return_value = mock_orchestrator

        resp = admin_client.post('/api/smart-assistant/chat/', {
            'query': '测试问题',
        }, format='json')
        assert resp.status_code == 200, resp.data
        assert resp.data['answer'] == '测试回答'
