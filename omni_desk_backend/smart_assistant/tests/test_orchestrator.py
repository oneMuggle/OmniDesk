"""Tests for smart_assistant agent orchestrator."""

import json
from unittest.mock import patch, MagicMock

from django.test import TestCase

from smart_assistant.agent.orchestrator import AgentOrchestrator


class TestAgentOrchestrator(TestCase):
    """AgentOrchestrator 编排流程测试."""

    def setUp(self):
        self.orchestrator = AgentOrchestrator()

    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    @patch('smart_assistant.agent.orchestrator.generate_answer')
    def test_tool_route_success(self, mock_generate, mock_classify, mock_registry):
        """工具路由成功时返回工具结果."""
        mock_classify.return_value = 'schedule_query'

        mock_tool = MagicMock()
        mock_tool.name = 'schedule_query'
        mock_tool.execute.return_value = {
            'found': True,
            'schedules': [{'duty_date': '2026-05-05', 'duty_person': '张三', 'duty_leader': '李四'}],
        }
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{'name': 'schedule_query', 'description': 'test'}]

        mock_generate.return_value = '明天张三值班。'

        result = self.orchestrator.process('明天谁值班？')

        self.assertEqual(result['intent'], 'schedule_query')
        self.assertEqual(result['tool_used'], 'schedule_query')
        self.assertTrue(result['tool_result']['found'])
        mock_tool.execute.assert_called_once()

    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    @patch('smart_assistant.agent.orchestrator.generate_general_answer')
    def test_tool_fallback_to_general(self, mock_general, mock_classify, mock_registry):
        """工具返回 found=False 时 fallback 到通用回答."""
        mock_classify.return_value = 'schedule_query'

        mock_tool = MagicMock()
        mock_tool.name = 'schedule_query'
        mock_tool.execute.return_value = {'found': False, 'message': '无排班记录'}
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{'name': 'schedule_query', 'description': 'test'}]

        mock_general.return_value = '抱歉，暂无排班信息。'

        result = self.orchestrator.process('明天谁值班？')

        self.assertTrue(result['tool_fallback'])
        self.assertEqual(result['answer'], '抱歉，暂无排班信息。')

    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    @patch('smart_assistant.agent.orchestrator.generate_general_answer')
    def test_general_chat_no_tool(self, mock_general, mock_classify, mock_registry):
        """通用对话不使用工具."""
        mock_classify.return_value = 'general_chat'
        mock_registry.get_tool.return_value = None
        mock_registry.get_all_schemas.return_value = []
        mock_general.return_value = '你好！我是你的助手。'

        result = self.orchestrator.process('你好')

        self.assertEqual(result['intent'], 'general_chat')
        self.assertIsNone(result['tool_used'])
        self.assertEqual(result['answer'], '你好！我是你的助手。')

    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    @patch('smart_assistant.agent.orchestrator.generate_general_answer')
    def test_tool_exception_fallback(self, mock_general, mock_classify, mock_registry):
        """工具抛出异常时 fallback 到通用回答."""
        mock_classify.return_value = 'knowledge_qa'

        mock_tool = MagicMock()
        mock_tool.name = 'knowledge_qa'
        mock_tool.execute.side_effect = Exception('Ragflow connection failed')
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{'name': 'knowledge_qa', 'description': 'test'}]

        mock_general.return_value = '抱歉，暂时无法回答。'

        result = self.orchestrator.process('查询文档')

        self.assertTrue(result['tool_fallback'])
        self.assertEqual(result['answer'], '抱歉，暂时无法回答。')

    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    @patch('smart_assistant.agent.orchestrator.generate_answer')
    def test_sources_extracted(self, mock_generate, mock_classify, mock_registry):
        """工具返回中包含 sources 时正确提取."""
        mock_classify.return_value = 'knowledge_qa'

        mock_tool = MagicMock()
        mock_tool.name = 'knowledge_qa'
        mock_tool.execute.return_value = {
            'found': True,
            'context': 'some context',
            'sources': [{'document': 'test.pdf', 'score': 0.9}],
        }
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{'name': 'knowledge_qa', 'description': 'test'}]
        mock_generate.return_value = '根据知识库...'

        result = self.orchestrator.process('查询')

        self.assertIsNotNone(result['sources'])
        self.assertEqual(result['sources'][0]['document'], 'test.pdf')

    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    @patch('smart_assistant.agent.orchestrator.generate_answer')
    def test_conversation_history_passed_to_tool(self, mock_generate, mock_classify, mock_registry):
        """对话历史传递给工具."""
        mock_classify.return_value = 'schedule_query'

        mock_tool = MagicMock()
        mock_tool.name = 'schedule_query'
        mock_tool.execute.return_value = {'found': True, 'schedules': []}
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{'name': 'schedule_query', 'description': 'test'}]
        mock_generate.return_value = '回答'

        history = [{'role': 'user', 'content': '今天天气如何'}]
        result = self.orchestrator.process('明天谁值班？', conversation_history=history)

        call_kwargs = mock_tool.execute.call_args[1]
        self.assertEqual(call_kwargs['context']['history'], history)


class TestAgentOrchestratorStream(TestCase):
    """AgentOrchestrator 流式处理测试."""

    def setUp(self):
        self.orchestrator = AgentOrchestrator()

    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    @patch('smart_assistant.agent.orchestrator.generate_answer_stream')
    def test_stream_meta_then_chunks(self, mock_stream, mock_classify, mock_registry):
        """流式处理先发送 meta 再发送 chunk."""
        mock_classify.return_value = 'schedule_query'

        mock_tool = MagicMock()
        mock_tool.name = 'schedule_query'
        mock_tool.execute.return_value = {'found': True, 'schedules': []}
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{'name': 'schedule_query', 'description': 'test'}]

        mock_stream.return_value = iter(['你好', '这是', '回答'])

        chunks = list(self.orchestrator.process_stream('问题'))

        # 第一个 chunk 是 meta
        first_data = chunks[0].split('data: ', 1)[1]
        meta = json.loads(first_data)
        self.assertEqual(meta['type'], 'meta')
        self.assertEqual(meta['intent'], 'schedule_query')

        # 后续是 content chunks
        content_chunks = [c for c in chunks[1:] if '"content"' in c]
        self.assertEqual(len(content_chunks), 3)

        # 最后一个是 done 信号
        last_data = chunks[-1].split('data: ', 1)[1]
        done = json.loads(last_data)
        self.assertEqual(done['type'], 'done')

    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    @patch('smart_assistant.agent.orchestrator.generate_general_answer')
    def test_stream_general_chat_no_tool(self, mock_general, mock_classify, mock_registry):
        """通用对话流式处理."""
        mock_classify.return_value = 'general_chat'
        mock_registry.get_tool.return_value = None
        mock_registry.get_all_schemas.return_value = []
        mock_general.return_value = '通用回答'

        chunks = list(self.orchestrator.process_stream('你好'))

        # 应该有 meta + content + done
        self.assertTrue(len(chunks) >= 2)
        first_data = chunks[0].split('data: ', 1)[1]
        meta = json.loads(first_data)
        self.assertEqual(meta['type'], 'meta')
        self.assertIsNone(meta['tool_used'])
