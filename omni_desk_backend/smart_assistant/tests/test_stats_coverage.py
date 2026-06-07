"""Tests for smart_assistant StatsViewSet — 覆盖率补齐.

目标:views/stats.py 42% → 80%+。
覆盖 3 个 @action 端点:overview / daily / datasets。
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import CustomUser
from smart_assistant.models import AgentLog, KnowledgeDataset, SmartAssistantSession


class TestStatsViewSetOverview(TestCase):
    """GET /api/smart-assistant/stats/overview/ — 总体统计."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser', password='password123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.session = SmartAssistantSession.objects.create(
            user=self.user, title='测试会话'
        )

    def _create_log(self, **kwargs):
        defaults = {
            'session': self.session,
            'user_query': '默认问题',
            'intent': 'general_chat',
            'tool_used': '',
            'tool_input': {},
            'tool_output': {},
            'llm_response': '默认回答',
            'total_tokens': 100,
            'estimated_cost': 0.001,
            'response_time_ms': 200,
            'tool_success': None,
            'user_feedback': '',
        }
        defaults.update(kwargs)
        return AgentLog.objects.create(**defaults)

    def test_overview_no_data_returns_zero_defaults(self):
        """无日志时所有统计指标归零,无除零异常."""
        response = self.client.get('/api/smart-assistant/stats/overview/')

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data['total_conversations'], 0)
        self.assertEqual(data['active_users'], 0)
        self.assertEqual(data['total_tokens'], 0)
        self.assertEqual(data['tool_success_rate'], 0)
        self.assertEqual(data['feedback_up'], 0)
        self.assertEqual(data['feedback_down'], 0)
        self.assertEqual(data['unrecognized'], 0)
        self.assertEqual(data['period_days'], 30)

    def test_overview_with_logs_aggregates_correctly(self):
        """多条日志时聚合正确(总数/token/成本/反馈/工具成功率)."""
        self._create_log(
            user_query='查排班',
            intent='schedule_query',
            tool_used='schedule_query',
            tool_success=True,
            total_tokens=200,
            estimated_cost=0.002,
            response_time_ms=300,
            user_feedback='up',
        )
        self._create_log(
            user_query='闲聊',
            intent='general_chat',
            tool_used='',
            tool_success=False,
            total_tokens=50,
            estimated_cost=0.0005,
            response_time_ms=100,
            user_feedback='down',
        )
        self._create_log(
            user_query='查人员',
            intent='personnel_query',
            tool_used='personnel_query',
            tool_success=True,
            total_tokens=150,
            estimated_cost=0.0015,
            response_time_ms=250,
        )

        response = self.client.get('/api/smart-assistant/stats/overview/')
        self.assertEqual(response.status_code, 200)
        data = response.data

        self.assertEqual(data['total_conversations'], 3)
        self.assertEqual(data['active_users'], 1)
        self.assertEqual(data['total_tokens'], 400)  # 200+50+150
        # 2 条 tool_used 非空(schedule/personnel)且都 tool_success=True = 100%
        self.assertEqual(data['tool_success_rate'], 100.0)
        self.assertEqual(data['feedback_up'], 1)
        self.assertEqual(data['feedback_down'], 1)
        # intent_breakdown 应包含 3 个意图
        self.assertEqual(data['intent_breakdown']['schedule_query'], 1)
        self.assertEqual(data['intent_breakdown']['personnel_query'], 1)
        # top_questions 应包含 3 个问题
        self.assertEqual(len(data['top_questions']), 3)
        # unrecognized = intent='general_chat' 的日志数
        self.assertEqual(data['unrecognized'], 1)

    def test_overview_respects_days_parameter(self):
        """days 参数控制统计时间窗口."""
        # 创建 50 天前的旧日志
        old_log = self._create_log(user_query='旧问题')
        AgentLog.objects.filter(pk=old_log.pk).update(
            created_at=timezone.now() - timedelta(days=50)
        )
        # 创建今天的日志
        self._create_log(user_query='新问题')

        # 默认 30 天
        response = self.client.get('/api/smart-assistant/stats/overview/')
        self.assertEqual(response.data['total_conversations'], 1)
        self.assertEqual(response.data['period_days'], 30)

        # 60 天应包含旧日志
        response = self.client.get('/api/smart-assistant/stats/overview/?days=60')
        self.assertEqual(response.data['total_conversations'], 2)
        self.assertEqual(response.data['period_days'], 60)

        # 7 天只剩新日志
        response = self.client.get('/api/smart-assistant/stats/overview/?days=7')
        self.assertEqual(response.data['total_conversations'], 1)

    def test_overview_tool_success_rate_handles_zero_total(self):
        """tool_total_count=0 时 tool_success_rate=0(无除零异常)."""
        # 只创建无 tool_used 的日志
        self._create_log(user_query='无工具', tool_used='')

        response = self.client.get('/api/smart-assistant/stats/overview/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['tool_success_rate'], 0)

    def test_overview_excludes_empty_tool_used_from_breakdown(self):
        """tool_breakdown 应排除 tool_used 为空字符串的日志(model NOT NULL)."""
        self._create_log(user_query='有工具', tool_used='schedule_query')
        self._create_log(user_query='空工具1', tool_used='')
        self._create_log(user_query='空工具2', tool_used='')

        response = self.client.get('/api/smart-assistant/stats/overview/')
        self.assertEqual(response.status_code, 200)
        # tool_breakdown 不应包含空字符串键
        self.assertNotIn('', response.data['tool_breakdown'])
        self.assertIn('schedule_query', response.data['tool_breakdown'])
        # 但 stats 仍计入有 tool_used 的部分(schedule_query=1)
        self.assertEqual(response.data['tool_breakdown']['schedule_query'], 1)


class TestStatsViewSetDaily(TestCase):
    """GET /api/smart-assistant/stats/daily/ — 每日趋势."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser', password='password123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.session = SmartAssistantSession.objects.create(
            user=self.user, title='测试会话'
        )

    def test_daily_empty_returns_empty_list(self):
        """无日志时 daily_stats 为空列表."""
        response = self.client.get('/api/smart-assistant/stats/daily/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['daily_stats'], [])

    def test_daily_groups_by_date(self):
        """同一天的多条日志应聚合为一行."""
        today = timezone.now()
        # 创建 3 条今天的日志 + 2 条昨天的日志
        for i in range(3):
            log = AgentLog.objects.create(
                session=self.session,
                user_query=f'今天问题{i}',
                intent='general_chat',
                llm_response='回答',
                total_tokens=100,
                response_time_ms=200,
            )
            AgentLog.objects.filter(pk=log.pk).update(created_at=today)

        yesterday = today - timedelta(days=1)
        for i in range(2):
            log = AgentLog.objects.create(
                session=self.session,
                user_query=f'昨天问题{i}',
                intent='general_chat',
                llm_response='回答',
                total_tokens=50,
                response_time_ms=100,
            )
            AgentLog.objects.filter(pk=log.pk).update(created_at=yesterday)

        response = self.client.get('/api/smart-assistant/stats/daily/')
        self.assertEqual(response.status_code, 200)
        stats = response.data['daily_stats']
        self.assertEqual(len(stats), 2)

        # 第一天 conversations=3, 第二天 conversations=2
        # (按 date 升序,昨天的在前)
        self.assertEqual(stats[0]['conversations'], 2)
        self.assertEqual(stats[1]['conversations'], 3)

    def test_daily_respects_days_parameter(self):
        """days 参数控制时间窗口."""
        # 50 天前的日志应被 30 天默认窗口排除
        old_log = AgentLog.objects.create(
            session=self.session,
            user_query='旧',
            intent='general_chat',
            llm_response='r',
        )
        AgentLog.objects.filter(pk=old_log.pk).update(
            created_at=timezone.now() - timedelta(days=50)
        )
        # 今天的日志
        AgentLog.objects.create(
            session=self.session,
            user_query='新',
            intent='general_chat',
            llm_response='r',
        )

        # 默认 30 天
        response = self.client.get('/api/smart-assistant/stats/daily/')
        self.assertEqual(len(response.data['daily_stats']), 1)

        # 60 天应包含旧日志
        response = self.client.get('/api/smart-assistant/stats/daily/?days=60')
        self.assertEqual(len(response.data['daily_stats']), 2)


class TestStatsViewSetDatasets(TestCase):
    """GET /api/smart-assistant/stats/datasets/ — 数据集列表."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser', password='password123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_datasets_returns_active_ordered_by_priority(self):
        """只返回 is_active=True 的数据集,按 priority+name 排序."""
        KnowledgeDataset.objects.create(
            name='低优先级',
            ragflow_dataset_id='rag-1',
            is_active=True,
            priority=10,
            description='desc1',
            tags=['tag1'],
            document_count=5,
        )
        KnowledgeDataset.objects.create(
            name='高优先级',
            ragflow_dataset_id='rag-2',
            is_active=True,
            priority=1,
            description='desc2',
            tags=['tag2', 'tag3'],
            document_count=10,
        )
        KnowledgeDataset.objects.create(
            name='已停用',
            ragflow_dataset_id='rag-3',
            is_active=False,
            priority=0,
        )

        response = self.client.get('/api/smart-assistant/stats/datasets/')
        self.assertEqual(response.status_code, 200)
        datasets = response.data['datasets']
        # 停用的不应出现
        self.assertEqual(len(datasets), 2)
        # priority=1 在前
        self.assertEqual(datasets[0]['name'], '高优先级')
        self.assertEqual(datasets[0]['document_count'], 10)
        self.assertEqual(datasets[0]['tags'], ['tag2', 'tag3'])
        self.assertEqual(datasets[1]['name'], '低优先级')

    def test_datasets_empty_returns_empty_list(self):
        """无数据集时 datasets 为空列表."""
        response = self.client.get('/api/smart-assistant/stats/datasets/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['datasets'], [])

    def test_datasets_unauthenticated_returns_401(self):
        """未认证时返回 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/smart-assistant/stats/datasets/')
        self.assertEqual(response.status_code, 401)
