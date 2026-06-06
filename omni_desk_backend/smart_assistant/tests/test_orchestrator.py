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

        mock_generate.return_value = ('明天张三值班。', None)

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

        mock_general.return_value = ('抱歉，暂无排班信息。', None)

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
        mock_general.return_value = ('你好！我是你的助手。', None)

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

        mock_general.return_value = ('抱歉，暂时无法回答。', None)

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
        mock_generate.return_value = ('根据知识库...', None)

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
        mock_generate.return_value = ('回答', None)

        history = [{'role': 'user', 'content': '今天天气如何'}]
        result = self.orchestrator.process('明天谁值班？', conversation_history=history)

        call_kwargs = mock_tool.execute.call_args[1]
        self.assertEqual(call_kwargs['context']['history'], history)

    @patch('smart_assistant.agent.orchestrator.cache_intent')
    @patch('smart_assistant.agent.orchestrator.get_cached_intent')
    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    @patch('smart_assistant.agent.orchestrator.generate_answer')
    def test_intent_cache_hit_skips_classifier(
        self, mock_generate, mock_classify, mock_registry, mock_get_cached, mock_cache_intent
    ):
        """意图缓存命中时,classify_intent 不被调用,直接走工具路由."""
        # 预填 intent 缓存
        mock_get_cached.return_value = 'schedule_query'

        mock_tool = MagicMock()
        mock_tool.name = 'schedule_query'
        mock_tool.execute.return_value = {'found': True, 'schedules': []}
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{'name': 'schedule_query', 'description': 'test'}]
        mock_generate.return_value = ('张三值班。', None)

        result = self.orchestrator.process('明天谁值班？')

        # 缓存命中 → classify_intent 不应被调用
        mock_classify.assert_not_called()
        mock_get_cached.assert_called_once()
        # 命中已有值,不应再写入
        mock_cache_intent.assert_not_called()
        # 工具路由仍正常完成
        self.assertEqual(result['intent'], 'schedule_query')
        self.assertEqual(result['tool_used'], 'schedule_query')

    @patch('smart_assistant.agent.orchestrator.cache_intent')
    @patch('smart_assistant.agent.orchestrator.get_cached_intent')
    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    @patch('smart_assistant.agent.orchestrator.generate_answer')
    def test_has_history_skips_intent_cache(
        self, mock_generate, mock_classify, mock_registry, mock_get_cached, mock_cache_intent
    ):
        """有对话历史时不读/不写意图缓存(避免历史依赖被错误缓存)."""
        mock_classify.return_value = 'schedule_query'

        mock_tool = MagicMock()
        mock_tool.name = 'schedule_query'
        mock_tool.execute.return_value = {'found': True, 'schedules': []}
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{'name': 'schedule_query', 'description': 'test'}]
        mock_generate.return_value = ('回答', None)

        history = [{'role': 'user', 'content': '上周谁值班？'}]
        result = self.orchestrator.process('这周呢？', conversation_history=history)

        # has_history=True → 既不读也不写 intent 缓存
        mock_get_cached.assert_not_called()
        mock_cache_intent.assert_not_called()
        # classify_intent 仍被调用(传 history)
        mock_classify.assert_called_once()
        self.assertEqual(result['intent'], 'schedule_query')

    @patch('smart_assistant.agent.orchestrator.synthesize_chain_answer')
    @patch('smart_assistant.agent.orchestrator.execute_tool_chain')
    @patch('smart_assistant.agent.orchestrator.generate_tool_chain_plan')
    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    def test_process_chain_returns_multi_tool_results(
        self, mock_classify, mock_registry, mock_plan, mock_execute, mock_synthesize
    ):
        """多工具链返回时,answer 来自 synthesize,tool_result 包含 chain_results 与 sources."""
        mock_classify.return_value = 'multi_tool_chain'
        mock_registry.get_all_schemas.return_value = [
            {'name': 'schedule_query', 'description': '排班'},
            {'name': 'personnel_query', 'description': '人员'},
        ]

        # LLM 规划返回 2 个工具的链
        mock_plan.return_value = [
            {'tool': 'schedule_query', 'params': {}, 'depends_on': None},
            {'tool': 'personnel_query', 'params': {'uid': '$schedule_query.user_id'}, 'depends_on': 'schedule_query'},
        ]

        # 执行器返回 2 个工具的结果(含 sources)
        mock_execute.return_value = [
            {
                'tool_name': 'schedule_query',
                'result': {
                    'found': True,
                    'schedules': [],
                    'sources': [{'document': 'duty.pdf', 'score': 0.9}],
                },
                'success': True,
            },
            {
                'tool_name': 'personnel_query',
                'result': {
                    'found': True,
                    'user_id': 42,
                    'sources': [{'document': 'hr.xlsx', 'score': 0.8}],
                },
                'success': True,
            },
        ]
        mock_synthesize.return_value = '张三这周值班且是研发部工程师。'

        result = self.orchestrator.process('张三这周值班情况和他的部门信息')

        # 多工具链走 _process_chain 路径
        self.assertEqual(result['intent'], 'multi_tool_chain')
        self.assertEqual(result['answer'], '张三这周值班且是研发部工程师。')
        # tool_used 取 plan 的第一个工具
        self.assertEqual(result['tool_used'], 'schedule_query')
        # tool_result 包裹 chain_results
        self.assertIn('chain_results', result['tool_result'])
        self.assertEqual(len(result['tool_result']['chain_results']), 2)
        # sources 合并了两个工具的来源
        self.assertIsNotNone(result['sources'])
        self.assertEqual(len(result['sources']), 2)
        # 整个 plan 透传
        self.assertEqual(len(result['tool_chain']), 2)

    @patch('smart_assistant.agent.orchestrator.ToolRegistry')
    @patch('smart_assistant.agent.orchestrator.classify_intent')
    @patch('smart_assistant.agent.orchestrator.generate_general_answer')
    def test_tool_fallback_response_structure(
        self, mock_general, mock_classify, mock_registry
    ):
        """工具返回 found=False 时,返回结构完整含 tool_fallback=True 且 sources=None."""
        mock_classify.return_value = 'schedule_query'

        mock_tool = MagicMock()
        mock_tool.name = 'schedule_query'
        mock_tool.execute.return_value = {
            'found': False,
            'message': '本周无排班',
        }
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{'name': 'schedule_query', 'description': 'test'}]
        mock_general.return_value = ('抱歉,暂无排班。', {'total_tokens': 20})

        result = self.orchestrator.process('明天谁值班？')

        # 必备字段
        self.assertIn('answer', result)
        self.assertIn('intent', result)
        self.assertIn('tool_used', result)
        self.assertIn('tool_result', result)
        self.assertIn('sources', result)
        self.assertIn('tool_fallback', result)
        self.assertIn('usage', result)

        self.assertEqual(result['answer'], '抱歉,暂无排班。')
        self.assertEqual(result['intent'], 'schedule_query')
        self.assertEqual(result['tool_used'], 'schedule_query')
        self.assertEqual(result['tool_result']['found'], False)
        self.assertIsNone(result['sources'])
        self.assertTrue(result['tool_fallback'])
        self.assertEqual(result['usage'], {'total_tokens': 20})


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
        mock_general.return_value = ('通用回答', None)

        chunks = list(self.orchestrator.process_stream('你好'))

        # 应该有 meta + content + done
        self.assertTrue(len(chunks) >= 2)
        first_data = chunks[0].split('data: ', 1)[1]
        meta = json.loads(first_data)
        self.assertEqual(meta['type'], 'meta')
        self.assertIsNone(meta['tool_used'])
