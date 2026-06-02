"""Tests for smart_assistant API views."""

import json
from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from users.models import CustomUser
from smart_assistant.models import KnowledgeBaseDocument, SmartAssistantSession, AgentLog
from smart_assistant.agent.orchestrator import AgentOrchestrator


class TestSmartChatViewSet(TestCase):
    """SmartChatViewSet 聊天 API 测试."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='password123',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch.object(AgentOrchestrator, 'process')
    def test_chat_success(self, mock_process):
        """POST /api/smart-assistant/chat/ 成功返回."""
        mock_process.return_value = {
            'answer': '明天张三值班。',
            'intent': 'schedule_query',
            'tool_used': 'schedule_query',
            'tool_result': {'found': True},
            'sources': None,
        }

        response = self.client.post(
            '/api/smart-assistant/chat/',
            {'query': '明天谁值班？'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['answer'], '明天张三值班。')
        self.assertEqual(response.data['intent'], 'schedule_query')

    def test_chat_missing_query(self):
        """缺少 query 参数时返回 400."""
        response = self.client.post(
            '/api/smart-assistant/chat/',
            {},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('smart_assistant.agent.orchestrator.AgentOrchestrator')
    def test_chat_creates_session(self, mock_orchestrator_cls):
        """不带 conversation_id 时自动创建新会话."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process.return_value = {
            'answer': '回答',
            'intent': 'general_chat',
            'tool_used': None,
            'tool_result': None,
            'sources': None,
        }
        mock_orchestrator_cls.return_value = mock_orchestrator

        response = self.client.post(
            '/api/smart-assistant/chat/',
            {'query': '你好'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('conversation_id', response.data)

    @patch('smart_assistant.agent.orchestrator.AgentOrchestrator')
    def test_chat_with_conversation_id(self, mock_orchestrator_cls):
        """带 conversation_id 时复用已有会话."""
        session = SmartAssistantSession.objects.create(
            user=self.user,
            title='测试会话',
            messages=[],
        )

        mock_orchestrator = MagicMock()
        mock_orchestrator.process.return_value = {
            'answer': '回答',
            'intent': 'general_chat',
            'tool_used': None,
            'tool_result': None,
            'sources': None,
        }
        mock_orchestrator_cls.return_value = mock_orchestrator

        response = self.client.post(
            '/api/smart-assistant/chat/',
            {'query': '继续', 'conversation_id': session.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_chat_unauthenticated(self):
        """未认证时返回 401."""
        self.client.force_authenticate(user=None)
        response = self.client.post(
            '/api/smart-assistant/chat/',
            {'query': '你好'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestSessionViewSet(TestCase):
    """SessionViewSet 会话管理测试."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='password123',
        )
        self.other_user = CustomUser.objects.create_user(
            username='otheruser',
            password='password123',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_own_sessions(self):
        """仅列出当前用户的会话."""
        SmartAssistantSession.objects.create(
            user=self.user, title='我的会话'
        )
        SmartAssistantSession.objects.create(
            user=self.other_user, title='别人的会话'
        )

        response = self.client.get('/api/smart-assistant/sessions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['title'], '我的会话')

    def test_delete_own_session(self):
        """可以删除自己的会话."""
        session = SmartAssistantSession.objects.create(
            user=self.user, title='要删除的会话'
        )

        response = self.client.delete(
            f'/api/smart-assistant/sessions/{session.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SmartAssistantSession.objects.filter(id=session.id).exists())

    def test_cannot_delete_other_user_session(self):
        """不能删除别人的会话（404 因为 queryset 过滤）。"""
        session = SmartAssistantSession.objects.create(
            user=self.other_user, title='别人的会话'
        )

        response = self.client.delete(
            f'/api/smart-assistant/sessions/{session.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestKnowledgeBaseViewSet(TestCase):
    """KnowledgeBaseViewSet 知识库管理测试."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='password123',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch('smart_assistant.views.knowledge_base.process_document_embedding')
    def test_upload_document_triggers_task(self, mock_task):
        """上传文档时触发异步向量化任务."""
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile

        file_content = b'test document content'
        uploaded_file = SimpleUploadedFile(
            'test.txt',
            file_content,
            content_type='text/plain',
        )

        response = self.client.post(
            '/api/smart-assistant/knowledge-base/documents/',
            {'title': '测试文档', 'file': uploaded_file},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_task.delay.assert_called_once()

    def test_list_own_documents(self):
        """仅列出当前用户上传的文档."""
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile

        other_user = CustomUser.objects.create_user(
            username='otheruser',
            password='password123',
        )

        file1 = SimpleUploadedFile('my.txt', b'content', content_type='text/plain')
        file2 = SimpleUploadedFile('other.txt', b'content', content_type='text/plain')

        KnowledgeBaseDocument.objects.create(
            title='我的文档', uploaded_by=self.user, file=file1
        )
        KnowledgeBaseDocument.objects.create(
            title='别人的文档', uploaded_by=other_user, file=file2
        )

        response = self.client.get('/api/smart-assistant/knowledge-base/documents/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)


class TestAgentLogViewSet(TestCase):
    """AgentLogViewSet 审计日志测试."""

    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin',
            password='password123',
            is_staff=True,
        )
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='password123',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        session = SmartAssistantSession.objects.create(
            user=self.user,
            title='测试会话',
        )
        AgentLog.objects.create(
            session=session,
            user_query='明天谁值班？',
            intent='schedule_query',
            tool_used='schedule_query',
            tool_input={'query': '明天谁值班？'},
            tool_output={'found': True},
            llm_response='明天张三值班。',
        )

    def test_list_logs(self):
        """列出审计日志."""
        response = self.client.get('/api/smart-assistant/agent-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_filter_by_intent(self):
        """按意图过滤."""
        response = self.client.get(
            '/api/smart-assistant/agent-logs/',
            {'intent': 'schedule_query'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_filter_by_keyword(self):
        """关键词搜索."""
        response = self.client.get(
            '/api/smart-assistant/agent-logs/',
            {'keyword': '值班'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_retrieve_log_detail(self):
        """获取日志详情."""
        log = AgentLog.objects.first()
        response = self.client.get(
            f'/api/smart-assistant/agent-logs/{log.id}/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_query'], '明天谁值班？')
