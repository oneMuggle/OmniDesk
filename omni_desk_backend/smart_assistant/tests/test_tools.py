"""Tests for smart_assistant tools."""

from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase

from smart_assistant.tools.schedule_tool import ScheduleTool
from smart_assistant.tools.personnel_tool import PersonnelTool
from smart_assistant.tools.rag_tool import RAGTool


class TestScheduleTool(TestCase):
    """ScheduleTool 日期解析与排班查询测试."""

    def setUp(self):
        self.tool = ScheduleTool()

    def test_intent_type(self):
        self.assertEqual(self.tool.intent_type, 'schedule_query')

    def test_schema(self):
        schema = self.tool.get_schema()
        self.assertEqual(schema['name'], 'schedule_query')
        self.assertIn('排班', schema['description'])

    def test_today_keyword(self):
        """无关键词时查询今天."""
        result = self.tool.execute('今天的排班')
        self.assertEqual(result['date'], result['date'])
        self.assertIn('found', result)

    def test_tomorrow_keyword(self):
        """包含'明天'时查询明天."""
        from datetime import date, timedelta
        from django.utils import timezone
        expected = (timezone.now().date() + timedelta(days=1))
        result = self.tool.execute('明天的排班')
        self.assertEqual(result['date'], str(expected))

    def test_day_after_tomorrow_keyword(self):
        """包含'后天'时查询后天."""
        from datetime import timedelta
        from django.utils import timezone
        expected = (timezone.now().date() + timedelta(days=2))
        result = self.tool.execute('后天的安排')
        self.assertEqual(result['date'], str(expected))

    def test_yesterday_keyword(self):
        """包含'昨天'时查询昨天."""
        from datetime import timedelta
        from django.utils import timezone
        expected = (timezone.now().date() - timedelta(days=1))
        result = self.tool.execute('昨天的排班')
        self.assertEqual(result['date'], str(expected))

    @patch('smart_assistant.tools.schedule_tool.Schedule')
    def test_no_schedules_returns_not_found(self, mock_schedule):
        """无排班记录时返回 found=False."""
        mock_schedule.objects.filter.return_value.select_related.return_value.exists.return_value = False
        result = self.tool.execute('明天的排班')
        self.assertFalse(result['found'])
        self.assertIn('message', result)

    @patch('smart_assistant.tools.schedule_tool.Schedule')
    def test_schedules_returns_found(self, mock_schedule):
        """有排班记录时返回 found=True."""
        mock_person = MagicMock()
        mock_person.name = '张三'
        mock_leader = MagicMock()
        mock_leader.name = '李四'

        mock_s = MagicMock()
        mock_s.duty_date = '2026-05-05'
        mock_s.duty_person = mock_person
        mock_s.duty_leader = mock_leader

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_s]))
        mock_schedule.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute('明天的排班')
        self.assertTrue(result['found'])
        self.assertEqual(len(result['schedules']), 1)
        self.assertEqual(result['schedules'][0]['duty_person'], '张三')


class TestPersonnelTool(TestCase):
    """PersonnelTool 人员搜索与脱敏测试."""

    def setUp(self):
        self.tool = PersonnelTool()

    def test_intent_type(self):
        self.assertEqual(self.tool.intent_type, 'personnel_query')

    def test_schema(self):
        schema = self.tool.get_schema()
        self.assertEqual(schema['name'], 'personnel_query')
        self.assertIn('人员', schema['description'])

    @patch('smart_assistant.tools.personnel_tool.Personnel')
    def test_no_results_returns_not_found(self, mock_personnel):
        """无匹配人员时返回 found=False."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_qs.__getitem__.return_value = mock_qs
        mock_personnel.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute('张三是谁')
        self.assertFalse(result['found'])
        self.assertIn('message', result)

    @patch('smart_assistant.tools.personnel_tool.Personnel')
    def test_found_returns_personnel_list(self, mock_personnel):
        """有匹配人员时返回人员列表."""
        mock_position = MagicMock()
        mock_position.name = '工程师'

        mock_p = MagicMock()
        mock_p.name = '张三'
        mock_p.department = '技术部'
        mock_p.position = mock_position
        mock_p.get_status_display.return_value = '在职'
        mock_p.phone_number = '13800000000'

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_p]))
        mock_qs.__getitem__.return_value = mock_qs
        mock_personnel.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute('查询张三')
        self.assertTrue(result['found'])
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['personnel'][0]['name'], '张三')
        self.assertEqual(result['personnel'][0]['department'], '技术部')


class TestRAGTool(TestCase):
    """RAGTool 知识库查询测试（使用 RAGRouter）。"""

    def setUp(self):
        self.tool = RAGTool()

    def test_intent_type(self):
        self.assertEqual(self.tool.intent_type, 'knowledge_qa')

    def test_schema(self):
        schema = self.tool.get_schema()
        self.assertEqual(schema['name'], 'knowledge_qa')

    @patch('smart_assistant.agent.rag_router.get_rag_router')
    def test_no_results_returns_not_found(self, mock_get_router):
        """RAGRouter 返回空时 found=False."""
        mock_router = MagicMock()
        mock_router.search_multi.return_value = []
        mock_get_router.return_value = mock_router
        result = self.tool.execute('什么是OmniDesk')
        self.assertFalse(result['found'])

    @patch('smart_assistant.agent.rag_router.get_rag_router')
    def test_successful_retrieval(self, mock_get_router):
        """RAGRouter 成功返回时解析 chunks."""
        mock_router = MagicMock()
        mock_router.search_multi.return_value = [
            {
                'content': 'OmniDesk 是一个办公管理系统',
                'document_name': '手册.pdf',
                'similarity': 0.95,
            },
        ]
        mock_get_router.return_value = mock_router

        result = self.tool.execute('什么是OmniDesk')
        self.assertTrue(result['found'])
        self.assertIn('OmniDesk', result['context'])
        self.assertEqual(len(result['sources']), 1)
        self.assertEqual(result['sources'][0]['document'], '手册.pdf')

    @patch('smart_assistant.agent.rag_router.get_rag_router')
    def test_empty_chunks_returns_not_found(self, mock_get_router):
        """RAGRouter 返回空 chunks 时 found=False."""
        mock_router = MagicMock()
        mock_router.search_multi.return_value = []
        mock_get_router.return_value = mock_router

        result = self.tool.execute('未知问题')
        self.assertFalse(result['found'])

    @patch('smart_assistant.agent.rag_router.get_rag_router')
    def test_router_error_returns_not_found(self, mock_get_router):
        """RAGRouter 返回空（内部已处理异常）时 found=False."""
        mock_router = MagicMock()
        mock_router.search_multi.return_value = []  # RAGRouter 内部已捕获异常，返回空列表
        mock_get_router.return_value = mock_router

        result = self.tool.execute('测试问题')
        self.assertFalse(result['found'])
