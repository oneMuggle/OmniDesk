"""EventTool 日期解析与排班/节假日查询测试.

对应交接文档任务 A.1:
- 日期范围解析(今天/明天/后天/昨天)
- 节假日边界(开始/中间/结束)
- 空查询(无排班无节假日)
- 跨年事件(12月31日 → 1月1日)

为快速稳定,基础测试使用 mock(无需 DB);
跨年和边界日期使用真实 DB(db fixture)以验证日期过滤逻辑。
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from django.utils import timezone

from smart_assistant.tools.event_tool import EventTool


# =============================================================================
# 1. 基本属性测试
# =============================================================================


class TestEventToolProperties(TestCase):
    """EventTool 类的元数据."""

    def setUp(self):
        self.tool = EventTool()

    def test_name(self):
        self.assertEqual(self.tool.name, "event_query")

    def test_description_contains_holiday_keyword(self):
        """描述应包含"节假日"或"排班"等关键词."""
        self.assertTrue(
            "节假日" in self.tool.description or "排班" in self.tool.description,
            f"description 应说明工具用途, 实际: {self.tool.description}",
        )

    def test_intent_type(self):
        self.assertEqual(self.tool.intent_type, "event_query")

    def test_schema(self):
        schema = self.tool.get_schema()
        self.assertEqual(schema["name"], "event_query")
        self.assertEqual(schema["description"], self.tool.description)
        self.assertEqual(schema["intent_type"], "event_query")


# =============================================================================
# 2. 日期关键词解析(无 DB,使用 mock 验证目标日期)
# =============================================================================


class TestEventToolDateParsing(TestCase):
    """EventTool 对不同日期关键词的解析."""

    def setUp(self):
        self.tool = EventTool()

    @patch("smart_assistant.tools.event_tool.Schedule")
    @patch("smart_assistant.tools.event_tool.Holiday")
    def test_default_no_keyword_uses_today(self, mock_holiday, mock_schedule):
        """无日期关键词时,查询今天."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_schedule.objects.filter.return_value.select_related.return_value = mock_qs
        mock_holiday.objects.filter.return_value.exists.return_value = False

        result = self.tool.execute("查询事件")
        self.assertEqual(result["date"], str(timezone.now().date()))

    @patch("smart_assistant.tools.event_tool.Schedule")
    @patch("smart_assistant.tools.event_tool.Holiday")
    def test_today_keyword(self, mock_holiday, mock_schedule):
        """包含"今天"时,目标日期为今天."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_schedule.objects.filter.return_value.select_related.return_value = mock_qs
        mock_holiday.objects.filter.return_value.exists.return_value = False

        result = self.tool.execute("今天有什么安排")
        self.assertEqual(result["date"], str(timezone.now().date()))

    @patch("smart_assistant.tools.event_tool.Schedule")
    @patch("smart_assistant.tools.event_tool.Holiday")
    def test_tomorrow_keyword(self, mock_holiday, mock_schedule):
        """包含"明天"时,目标日期为明天."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_schedule.objects.filter.return_value.select_related.return_value = mock_qs
        mock_holiday.objects.filter.return_value.exists.return_value = False

        expected = (timezone.now() + timedelta(days=1)).date()
        result = self.tool.execute("明天的排班")
        self.assertEqual(result["date"], str(expected))

    @patch("smart_assistant.tools.event_tool.Schedule")
    @patch("smart_assistant.tools.event_tool.Holiday")
    def test_day_after_tomorrow_keyword(self, mock_holiday, mock_schedule):
        """包含"后天"时,目标日期为后天."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_schedule.objects.filter.return_value.select_related.return_value = mock_qs
        mock_holiday.objects.filter.return_value.exists.return_value = False

        expected = (timezone.now() + timedelta(days=2)).date()
        result = self.tool.execute("后天有什么活动")
        self.assertEqual(result["date"], str(expected))

    @patch("smart_assistant.tools.event_tool.Schedule")
    @patch("smart_assistant.tools.event_tool.Holiday")
    def test_yesterday_keyword(self, mock_holiday, mock_schedule):
        """包含"昨天"时,目标日期为昨天."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_schedule.objects.filter.return_value.select_related.return_value = mock_qs
        mock_holiday.objects.filter.return_value.exists.return_value = False

        expected = (timezone.now() - timedelta(days=1)).date()
        result = self.tool.execute("昨天谁值班")
        self.assertEqual(result["date"], str(expected))

    @patch("smart_assistant.tools.event_tool.Schedule")
    @patch("smart_assistant.tools.event_tool.Holiday")
    def test_keyword_precedence_tomorrow_beats_default(self, mock_holiday, mock_schedule):
        """"明天" 关键词优先级高于默认(无关键词 → 今天)."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_schedule.objects.filter.return_value.select_related.return_value = mock_qs
        mock_holiday.objects.filter.return_value.exists.return_value = False

        t_today = self.tool.execute("今天")
        t_tomorrow = self.tool.execute("明天")
        t_default = self.tool.execute("无关键词查询")

        self.assertEqual(t_today["date"], t_default["date"], "今天 与 无关键词 都应返回今天")
        self.assertNotEqual(
            t_tomorrow["date"],
            t_today["date"],
            "明天 应返回不同日期",
        )


# =============================================================================
# 3. 查询结果场景(无 DB,使用 mock 验证返回结构)
# =============================================================================


class TestEventToolResultStructure(TestCase):
    """EventTool 返回结果的字段结构."""

    def setUp(self):
        self.tool = EventTool()

    @patch("smart_assistant.tools.event_tool.Schedule")
    @patch("smart_assistant.tools.event_tool.Holiday")
    def test_no_data_returns_not_found(self, mock_holiday, mock_schedule):
        """无排班无节假日时,found=False 且 message 非空."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_schedule.objects.filter.return_value.select_related.return_value = mock_qs
        mock_holiday.objects.filter.return_value.exists.return_value = False

        result = self.tool.execute("今天有什么")

        self.assertFalse(result["found"])
        self.assertIn("message", result)
        self.assertIn("date", result)
        self.assertNotIn("schedules", result, "无数据时不应返回 schedules 字段")
        self.assertNotIn("holidays", result, "无数据时不应返回 holidays 字段")

    @patch("smart_assistant.tools.event_tool.Schedule")
    @patch("smart_assistant.tools.event_tool.Holiday")
    def test_only_schedules_returns_found(self, mock_holiday, mock_schedule):
        """仅排班有数据时,found=True 且 schedules 非空,holidays 为空."""
        mock_person = MagicMock()
        mock_person.name = "张三"
        mock_leader = MagicMock()
        mock_leader.name = "李四"

        mock_s = MagicMock()
        mock_s.duty_date = date(2026, 5, 5)
        mock_s.duty_person = mock_person
        mock_s.duty_leader = mock_leader

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_s]))
        mock_schedule.objects.filter.return_value.select_related.return_value = mock_qs
        mock_holiday.objects.filter.return_value.exists.return_value = False

        result = self.tool.execute("明天的排班")

        self.assertTrue(result["found"])
        self.assertEqual(len(result["schedules"]), 1)
        self.assertEqual(result["schedules"][0]["duty_person"], "张三")
        self.assertEqual(result["schedules"][0]["duty_leader"], "李四")
        self.assertEqual(result["holidays"], [])

    @patch("smart_assistant.tools.event_tool.Schedule")
    @patch("smart_assistant.tools.event_tool.Holiday")
    def test_only_holidays_returns_found(self, mock_holiday, mock_schedule):
        """仅节假日有数据时,found=True 且 holidays 非空,schedules 为空."""
        mock_h = MagicMock()
        mock_h.name = "国庆节"
        mock_h.start_date = date(2026, 10, 1)
        mock_h.end_date = date(2026, 10, 7)

        mock_holiday_qs = MagicMock()
        mock_holiday_qs.exists.return_value = True
        mock_holiday_qs.__iter__ = MagicMock(return_value=iter([mock_h]))
        mock_holiday.objects.filter.return_value = mock_holiday_qs

        mock_schedule_qs = MagicMock()
        mock_schedule_qs.exists.return_value = False
        mock_schedule.objects.filter.return_value.select_related.return_value = mock_schedule_qs

        result = self.tool.execute("今天是什么节日")

        self.assertTrue(result["found"])
        self.assertEqual(result["schedules"], [])
        self.assertEqual(len(result["holidays"]), 1)
        self.assertEqual(result["holidays"][0]["name"], "国庆节")

    @patch("smart_assistant.tools.event_tool.Schedule")
    @patch("smart_assistant.tools.event_tool.Holiday")
    def test_unassigned_duty_person_fallback(self, mock_holiday, mock_schedule):
        """duty_person/duty_leader 为 None 时,显示'未安排'."""
        mock_s = MagicMock()
        mock_s.duty_date = date(2026, 5, 5)
        mock_s.duty_person = None
        mock_s.duty_leader = None

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_s]))
        mock_schedule.objects.filter.return_value.select_related.return_value = mock_qs
        mock_holiday.objects.filter.return_value.exists.return_value = False

        result = self.tool.execute("明天的排班")

        self.assertTrue(result["found"])
        self.assertEqual(result["schedules"][0]["duty_person"], "未安排")
        self.assertEqual(result["schedules"][0]["duty_leader"], "未安排")


# =============================================================================
# 4. 节假日边界 + 跨年事件(需要真实 DB 验证日期过滤)
# =============================================================================
#
# 注意:EventTool 内部 `target_date` 仅由"今天/明天/后天/昨天" 4 个关键词控制,
# 不解析 query 中的 ISO 日期字符串(如 "2027-01-01")。
# 因此 DB 测试需要让 fixture 日期与 query 关键词派生出的日期对齐。
# 跨年测试利用"明天" - 跨年夜查询明天即可触发 1月1日匹配。
#


@pytest.mark.django_db
class TestEventToolHolidayBoundary:
    """节假日边界与跨年事件(需真实 DB)."""

    @pytest.fixture
    def tool(self):
        return EventTool()

    @pytest.fixture
    def today(self):
        """今日日期(避免依赖 timezone.now() 的固定快照)."""
        return timezone.now().date()

    def test_holiday_spans_today_found(self, db, tool, today):
        """节假日 start_date == today,end_date == today + 3,查询"今天"应匹配."""
        from events.models import Holiday

        Holiday.objects.create(
            name="端午节",
            start_date=today,
            end_date=today + timedelta(days=3),
        )

        result = tool.execute("今天的安排")

        assert result["found"] is True
        assert len(result["holidays"]) == 1
        assert result["holidays"][0]["name"] == "端午节"

    def test_holiday_spans_tomorrow_middle_found(self, db, tool, today):
        """节假日 start_date == today,查询"明天"(中间日期)应匹配."""
        from events.models import Holiday

        Holiday.objects.create(
            name="端午节",
            start_date=today,
            end_date=today + timedelta(days=3),
        )

        # 明天 = today + 1,在 [today, today+3] 范围内
        result = tool.execute("明天有什么")

        assert result["found"] is True
        assert len(result["holidays"]) == 1

    def test_holiday_boundary_end_matches(self, db, tool, today):
        """节假日 end_date = today + 2,查询"后天"(end_date)应匹配(闭区间)."""
        from events.models import Holiday

        Holiday.objects.create(
            name="端午节",
            start_date=today,
            end_date=today + timedelta(days=2),
        )

        # 后天 = today + 2 = end_date,应匹配
        result = tool.execute("后天呢")

        assert result["found"] is True
        assert len(result["holidays"]) == 1

    def test_holiday_outside_range_not_matches(self, db, tool, today):
        """节假日 end_date = today + 1,查询"后天"(超出)应不匹配."""
        from events.models import Holiday

        Holiday.objects.create(
            name="端午节",
            start_date=today,
            end_date=today + timedelta(days=1),
        )

        # 后天 = today + 2,超出 [today, today+1]
        result = tool.execute("后天的安排")

        assert result["found"] is False

    def test_year_boundary_via_tomorrow_keyword(self, db, tool, today):
        """跨年场景:跨年夜的"明天" = 元旦,应被元旦节假日匹配.

        利用:如果今天是 2026-12-31(跨年夜),"明天" = 2027-01-01。
        但 today 是动态的,所以此测试用相对值:让 Holiday 跨 today 与 today+1,
        然后 query "明天" = today+1,验证仍能匹配(实际为"跨日"测试)。
        """
        from events.models import Holiday

        # 模拟跨年:start_date = today,end_date = today + 1
        # 这是个最小跨年节假日
        Holiday.objects.create(
            name="跨年节假日",
            start_date=today,
            end_date=today + timedelta(days=1),
        )

        # 查询"明天" = today + 1 = end_date,应匹配
        result = tool.execute("明天呢")

        assert result["found"] is True
        assert len(result["holidays"]) == 1
        assert result["holidays"][0]["name"] == "跨年节假日"

    def test_year_boundary_explicit_dates(self, db, tool):
        """显式创建跨年节假日(2026-12-31 ~ 2027-01-02),验证 ORM 闭区间查询.

        此测试不依赖 EventTool 的 query 解析(因为它不解析 ISO 字符串),
        而是直接验证 ORM 边界条件:target_date 为 2027-01-01 时应匹配。
        我们通过 monkeypatch timezone.now() 让"今天"=2026-12-31,这样
        query "明天" 解析为 2027-01-01。
        """
        from unittest.mock import patch as _patch
        from events.models import Holiday

        Holiday.objects.create(
            name="元旦",
            start_date=date(2026, 12, 31),
            end_date=date(2027, 1, 2),
        )

        # mock timezone.now() 返回 2026-12-31,使"明天" = 2027-01-01
        fake_now = timezone.make_aware(timezone.datetime(2026, 12, 31, 12, 0, 0))
        with _patch("smart_assistant.tools.event_tool.timezone") as mock_tz:
            mock_tz.now.return_value = fake_now
            result = tool.execute("明天是什么节日")

        assert result["found"] is True, f"应匹配元旦节假日,实际结果: {result}"
        assert len(result["holidays"]) == 1
        assert result["holidays"][0]["name"] == "元旦"

    def test_schedule_and_holiday_coexist(self, db, tool, today):
        """同一天既有排班又有节假日时,都返回."""
        from events.models import Holiday, Schedule

        Schedule.objects.create(
            duty_date=today,
            duty_person=None,
            duty_leader=None,
        )
        Holiday.objects.create(
            name="特殊纪念日",
            start_date=today,
            end_date=today,
        )

        result = tool.execute("今天的安排")

        assert result["found"] is True
        assert len(result["schedules"]) == 1
        assert len(result["holidays"]) == 1
