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

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_success(self, mock_orchestrator_cls):
        """POST /api/smart-assistant/chat/ 成功返回."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process.return_value = {
            'answer': '明天张三值班。',
            'intent': 'schedule_query',
            'tool_used': 'schedule_query',
            'tool_result': {'found': True},
            'sources': None,
            'usage': None,
        }
        mock_orchestrator_cls.return_value = mock_orchestrator
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

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_creates_session(self, mock_orchestrator_cls):
        """不带 conversation_id 时自动创建新会话."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process.return_value = {
            'answer': '回答',
            'intent': 'general_chat',
            'tool_used': None,
            'tool_result': None,
            'sources': None,
            'usage': None,
        }
        mock_orchestrator_cls.return_value = mock_orchestrator

        response = self.client.post(
            '/api/smart-assistant/chat/',
            {'query': '你好'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('conversation_id', response.data)

    @patch('smart_assistant.views.chat.AgentOrchestrator')
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
            'usage': None,
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

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_with_nonexistent_conversation_id_creates_new_session(self, mock_orchestrator_cls):
        """conversation_id 不存在时,view 静默忽略并创建新会话."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process.return_value = {
            'answer': '新会话回答',
            'intent': 'general_chat',
            'tool_used': None,
            'tool_result': None,
            'sources': None,
            'usage': None,
        }
        mock_orchestrator_cls.return_value = mock_orchestrator

        # conversation_id 99999 不存在
        response = self.client.post(
            '/api/smart-assistant/chat/',
            {'query': '你好', 'conversation_id': 99999},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 应创建了一个新会话
        self.assertIn('conversation_id', response.data)
        # 验证新会话存在
        new_session = SmartAssistantSession.objects.get(id=response.data['conversation_id'])
        self.assertEqual(new_session.user, self.user)
        self.assertEqual(new_session.turn_count, 1)

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_turn_count_increments(self, mock_orchestrator_cls):
        """同一会话连续多次对话,turn_count 应递增."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process.return_value = {
            'answer': '回答',
            'intent': 'general_chat',
            'tool_used': None,
            'tool_result': None,
            'sources': None,
            'usage': None,
        }
        mock_orchestrator_cls.return_value = mock_orchestrator

        # 第一次对话
        r1 = self.client.post(
            '/api/smart-assistant/chat/',
            {'query': '问题1'},
            format='json',
        )
        session_id = r1.data['conversation_id']

        # 第二次对话(用 session_id)
        r2 = self.client.post(
            '/api/smart-assistant/chat/',
            {'query': '问题2', 'conversation_id': session_id},
            format='json',
        )

        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        session = SmartAssistantSession.objects.get(id=session_id)
        # count_turns 数 user 角色消息数,2 次对话 = 2 turns
        self.assertEqual(session.turn_count, 2)
        # messages 列表应有 4 条(2 user + 2 assistant)
        self.assertEqual(len(session.messages), 4)

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_title_truncated_to_50_chars(self, mock_orchestrator_cls):
        """超长 query(>50 字)作为 title 应被截断到 50 字."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process.return_value = {
            'answer': '回答',
            'intent': 'general_chat',
            'tool_used': None,
            'tool_result': None,
            'sources': None,
            'usage': None,
        }
        mock_orchestrator_cls.return_value = mock_orchestrator

        # 100 字的 query
        long_query = "查询" * 50  # 100 字
        response = self.client.post(
            '/api/smart-assistant/chat/',
            {'query': long_query},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        session = SmartAssistantSession.objects.get(id=response.data['conversation_id'])
        # title 截断到 50 字
        self.assertEqual(len(session.title), 50)
        self.assertEqual(session.title, long_query[:50])

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_tool_fallback_marks_log_as_failure(self, mock_orchestrator_cls):
        """orchestrator 返回 tool_fallback=True 时,AgentLog.tool_success=False."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process.return_value = {
            'answer': '工具失败,使用 fallback',
            'intent': 'schedule_query',
            'tool_used': 'schedule_query',
            'tool_result': {'found': False, 'message': '查询失败'},
            'sources': None,
            'usage': None,
            'tool_fallback': True,  # 关键
        }
        mock_orchestrator_cls.return_value = mock_orchestrator

        response = self.client.post(
            '/api/smart-assistant/chat/',
            {'query': '明天谁值班'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 验证 AgentLog 标记
        log = AgentLog.objects.filter(user_query='明天谁值班').first()
        self.assertIsNotNone(log)
        self.assertFalse(log.tool_success, "tool_fallback=True 时,tool_success 应为 False")

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_usage_parsed_into_agent_log(self, mock_orchestrator_cls):
        """usage 字典正确解析到 AgentLog 的 input/output/total_tokens 字段."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.process.return_value = {
            'answer': '回答',
            'intent': 'general_chat',
            'tool_used': None,
            'tool_result': None,
            'sources': None,
            'usage': {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'total_tokens': 150,
            },
            'model_name': 'deepseek-r1:1.5b',
        }
        mock_orchestrator_cls.return_value = mock_orchestrator

        response = self.client.post(
            '/api/smart-assistant/chat/',
            {'query': '测试用量追踪'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = AgentLog.objects.filter(user_query='测试用量追踪').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.input_tokens, 100)
        self.assertEqual(log.output_tokens, 50)
        self.assertEqual(log.total_tokens, 150)
        self.assertEqual(log.model_name, 'deepseek-r1:1.5b')

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_stream_endpoint_yields_sse_chunks(self, mock_orchestrator_cls):
        """流式 stream 端点产生 SSE 事件流."""
        mock_orchestrator = MagicMock()
        # ⚠️ MagicMock 的 __iter__ 默认返回空,需用 side_effect 让 process_stream 返回可迭代对象
        stream_chunks = [
            'data: {"type": "meta", "intent": "general_chat"}\n\n',
            'data: {"type": "chunk", "content": "你好"}\n\n',
            'data: {"type": "chunk", "content": "世界"}\n\n',
            'data: {"type": "done"}\n\n',
        ]
        mock_orchestrator.process_stream.side_effect = lambda *args, **kwargs: iter(stream_chunks)
        # 也设 process 返回,避免 patch 撤销后影响其他测试
        mock_orchestrator.process.return_value = {
            'answer': '你好世界',
            'intent': 'general_chat',
            'tool_used': None,
            'tool_result': None,
            'sources': None,
            'usage': None,
        }
        mock_orchestrator_cls.return_value = mock_orchestrator

        response = self.client.post(
            '/api/smart-assistant/chat/stream/',
            {'query': '流式测试'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # ⚠️ Django client 对 StreamingHttpResponse 需要用 list() 强制消费
        # 否则 view 内的 session 创建代码不执行(见交接文档坑 #6)
        chunks = list(response.streaming_content)
        # 验证 SSE 块
        self.assertGreater(len(chunks), 0)
        # 验证至少有一个 chunk 包含流式内容
        full_response = b''.join(chunks).decode('utf-8')
        self.assertIn('"type": "chunk"', full_response)
        self.assertIn('"content": "你好"', full_response)


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
