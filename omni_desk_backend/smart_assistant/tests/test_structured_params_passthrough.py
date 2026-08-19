"""I-2 结构化参数透传测试:LLM validated 中的结构化字段须到达工具执行。"""

import pytest
from unittest.mock import MagicMock, patch

from smart_assistant.agent.orchestrator import AgentOrchestrator
from smart_assistant.tools.office_read_tool import OfficeReadTool
from smart_assistant.tools.schedule_tool import ScheduleTool
from smart_assistant.tools.tool_context import ToolContext


@pytest.fixture
def tool_context():
    return ToolContext(user=None, scope="GLOBAL")


@pytest.mark.django_db
def test_execute_native_tool_passes_full_params_to_scope_tool(tool_context):
    """scope 工具收到完整 validated dict(而非仅 {'query': ...})。"""
    validated = {"query": "本周排班", "date_from": "2026-08-10", "date_to": "2026-08-16"}
    captured = {}

    class _SpySchedule(ScheduleTool):
        def execute(self, query=None, context=None, params=None, scope=None, qs=None):
            captured["params"] = params
            return {"found": True, "count": 0}

    with patch("smart_assistant.agent.native_tool_runner.execute_guarded",
               side_effect=lambda tool, **kw: tool.execute(**kw)):
        result = AgentOrchestrator()._execute_native_tool(_SpySchedule(), validated, tool_context)

    assert captured["params"] == validated


@pytest.mark.django_db
def test_execute_native_tool_passes_params_to_nonscope_tool(tool_context):
    """非 scope 工具(office_read)也收到 params。"""
    validated = {"query": "读第3段", "chunk_index": 2}
    captured = {}

    class _SpyOffice(OfficeReadTool):
        def execute(self, query=None, context=None, params=None, **kwargs):
            captured["params"] = params
            return {"found": True, "count": 0}

    with patch("smart_assistant.agent.native_tool_runner.execute_guarded",
               side_effect=lambda tool, **kw: tool.execute(**kw)):
        AgentOrchestrator()._execute_native_tool(_SpyOffice(), validated, tool_context)

    assert captured["params"] == validated


@pytest.mark.django_db
def test_schedule_uses_structured_date_range():
    """LLM 提供 date_from/date_to → ScheduleTool 按范围过滤(不再查今日)。"""
    tool = ScheduleTool()
    base_qs = MagicMock()
    qs = base_qs.filter.return_value
    qs.filter.return_value = qs
    # date_from/date_to 分支:调用 qs.filter(duty_date__gte=...) + (duty_date__lte=...)
    result = tool.execute(
        params={"query": "排班", "date_from": "2026-08-10", "date_to": "2026-08-16"},
        scope="GLOBAL", qs=base_qs,
    )
    # 按范围过滤而非默认日期(今日)
    assert base_qs.filter.called
    call_kwargs = base_qs.filter.call_args.kwargs
    assert call_kwargs.get("duty_date__gte") == "2026-08-10"
    assert call_kwargs.get("duty_date__lte") == "2026-08-16"
    assert "duty_date" not in call_kwargs  # 不按"今日"等值过滤


@pytest.mark.django_db
def test_office_read_uses_chunk_index():
    """LLM 提供 chunk_index=2 → OfficeReadTool 返回第 3 片。"""
    tool = OfficeReadTool()
    ctx = {"attachment": {"text": "甲 乙 丙 丁 戊", "filename": "a.txt"}}
    with patch("smart_assistant.tools.office_read_tool.OfficeExtractor.chunk_text",
               return_value=["片0", "片1", "片2", "片3"]):
        result = tool.execute(
            query="读第3段", params={"chunk_index": 2},
            context=ctx,  # attachment 无 chunk_index,须从 params 取
        )
    assert result["found"] is True
    assert result["chunks"] == ["片2"]
    assert result["summary"] == "已读取附件第 3/4 片"


@pytest.mark.django_db
def test_personnel_department_status_filter():
    """personnel 消费 department/status。"""
    from unittest.mock import MagicMock
    from smart_assistant.tools.personnel_tool import PersonnelTool
    tool = PersonnelTool()
    base_qs = MagicMock()
    qs = base_qs.filter.return_value
    qs.filter.return_value = qs
    tool.execute(
        params={"query": "人员", "department": "研发部", "status": "在职"},
        scope="GLOBAL", qs=base_qs,
    )
    # 至少触发一次按 department 的 filter
    filter_calls = [c for c in base_qs.filter.call_args_list] + \
                   [c for c in qs.filter.call_args_list]
    assert any("department" in c[1] for c in filter_calls)


@pytest.mark.django_db
def test_memo_is_completed_filter():
    """memo 消费 is_completed。"""
    from unittest.mock import MagicMock
    from smart_assistant.tools.memo_tool import MemoTool
    tool = MemoTool()
    base_qs = MagicMock()
    qs = base_qs.filter.return_value
    qs.filter.return_value = qs
    tool.execute(params={"query": "便签", "is_completed": True}, scope="GLOBAL", qs=base_qs)
    assert any("is_completed" in c[1] for c in base_qs.filter.call_args_list)


@pytest.mark.django_db
def test_news_limit_respected():
    """news 消费 limit(替换硬编码 [:10])。"""
    from unittest.mock import MagicMock
    from smart_assistant.tools.news_tool import NewsTool
    tool = NewsTool()
    base_qs = MagicMock()
    qs = base_qs.filter.return_value
    # spy 切片:记录 [:limit] 的 slice.stop
    slices = []

    def spy_getitem(self, s):
        slices.append(s)
        return self

    qs.__getitem__ = spy_getitem
    tool.execute(params={"query": "新闻", "limit": 3}, scope="GLOBAL", qs=base_qs)
    assert any(getattr(s, "stop", None) == 3 for s in slices)


@pytest.mark.django_db
def test_event_uses_structured_target_date():
    """event 消费结构化 target_date → 按该日期过滤(而非默认今天)。"""
    from datetime import date as _date
    from smart_assistant.tools.event_tool import EventTool
    tool = EventTool()
    base_qs = MagicMock()
    qs = base_qs.filter.return_value
    tool.execute(
        params={"query": "排班", "target_date": "2026-08-20"},
        scope="GLOBAL", qs=base_qs,
    )
    assert base_qs.filter.called
    call_kwargs = base_qs.filter.call_args.kwargs
    assert call_kwargs.get("duty_date") == _date(2026, 8, 20)
    assert "duty_date" in call_kwargs


@pytest.mark.django_db
def test_meeting_room_uses_structured_target_date():
    """meeting_room 消费结构化 target_date → 预订窗口按该日期开闭区间。"""
    from datetime import date as _date
    from smart_assistant.tools.meeting_room_tool import MeetingRoomTool
    tool = MeetingRoomTool()
    base_qs = MagicMock()
    rooms = base_qs.__getitem__.return_value
    rooms.exists.return_value = True  # 避免 found:False 短路
    bookings_qs = MagicMock()
    with patch(
        "smart_assistant.tools.meeting_room_tool.MeetingRoomBooking.objects.filter",
        return_value=bookings_qs,
    ) as mock_filter:
        tool.execute(
            params={"query": "会议室", "target_date": "2026-08-20"},
            scope="GLOBAL", qs=base_qs,
        )
    assert mock_filter.called
    call_kwargs = mock_filter.call_args.kwargs
    assert call_kwargs["start_time__gte"].date() == _date(2026, 8, 20)
    assert call_kwargs["start_time__lte"].date() == _date(2026, 8, 20)
