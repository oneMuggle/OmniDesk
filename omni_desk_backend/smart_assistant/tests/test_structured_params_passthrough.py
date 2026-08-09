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

    with patch("smart_assistant.agent.orchestrator.execute_guarded",
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

    with patch("smart_assistant.agent.orchestrator.execute_guarded",
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
