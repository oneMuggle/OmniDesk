"""F2 流式原生 tool_calls 测试(process_stream 缓冲工具轮 + 流式最终轮)。"""

import pytest
from unittest.mock import patch

from smart_assistant.agent.orchestrator import AgentOrchestrator


def _make_tool_call(name, args_json, call_id="call_1"):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": args_json},
    }


class _FakeCtx:
    user = None
    scope = None


class _FakeScheduleTool:
    """mock 工具桩:_execute_native_tool 已被 patch,此桩仅用于 get_tool_for_user
    返回值占位(不真正执行)。"""

    name = "schedule_query"
    require_confirmation = False

    @classmethod
    def validate_arguments(cls, args):
        return args


@pytest.mark.django_db
def test_streaming_native_tool_calls_executes_then_streams():
    """原生开启 + 首轮 tool_calls → 工具执行 → 流式最终轮。"""
    ctx = _FakeCtx()
    orch = AgentOrchestrator()

    # 第 1 轮:LLM 返回 schedule_query tool_call;第 2 轮:无工具(content)
    tool_calls_seq = [
        ("round0", "tool_calls", [_make_tool_call("schedule_query", '{"query": "明天排班"}')]),
        ("round1", "content", "明天是张三早班"),
    ]

    def fake_generate_with_tools(messages=None, **kwargs):
        tag, kind, payload = tool_calls_seq.pop(0)
        if kind == "tool_calls":
            return "", {}, payload
        return payload, {}, []

    with patch.object(orch.router, "generate_with_tools", side_effect=fake_generate_with_tools), \
         patch.object(orch.router, "generate", return_value=iter(["明天", "是", "张三", "早班"])), \
         patch("smart_assistant.agent.orchestrator.ToolRegistry.get_tool_for_user",
               return_value=_FakeScheduleTool()), \
         patch.object(orch, "_execute_native_tool",
                      return_value=({"found": True, "schedules": [{"duty_date": "2026-08-10"}]}, None, None)):
        events = list(orch.process_stream(
            "明天排班", [], ctx, use_native_tool_calls=True,
        ))

    data_blob = "\n".join(events)
    assert 'type": "chunk"' in data_blob
    assert "明天" in data_blob and "张三" in data_blob  # 流式最终轮 chunk
    assert 'finish_reason": "stop"' in data_blob


@pytest.mark.django_db
def test_streaming_native_no_tools_single_chunk():
    """原生开启但首轮无 tool_calls → 直接单 chunk 输出 content,不重生成。"""
    ctx = _FakeCtx()
    orch = AgentOrchestrator()

    with patch.object(orch.router, "generate_with_tools",
                      return_value=("直接回答", {}, [])), \
         patch.object(orch.router, "generate", side_effect=AssertionError("不应重生成")):
        events = list(orch.process_stream("你好", [], ctx, use_native_tool_calls=True))

    data_blob = "\n".join(events)
    assert "直接回答" in data_blob
    assert "AssertionError" not in data_blob


@pytest.mark.django_db
def test_streaming_native_disabled_uses_intent_path():
    """原生关闭 → 走现有 intent 路由(回归)。"""
    ctx = _FakeCtx()
    orch = AgentOrchestrator()

    with patch("smart_assistant.agent.orchestrator.classify_intent", return_value="general"), \
         patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan", return_value=[]), \
         patch("smart_assistant.agent.orchestrator.generate_general_answer",
               return_value=("普通回答", {})):
        events = list(orch.process_stream("你好", [], ctx, use_native_tool_calls=False))

    data_blob = "\n".join(events)
    assert "普通回答" in data_blob


@pytest.mark.django_db
def test_streaming_native_confirm_replay_passthrough():
    """流式原生路径写工具 → awaiting_confirmation + confirmation_token 事件。"""
    ctx = _FakeCtx()
    orch = AgentOrchestrator()
    confirm_meta = {
        "tool_calls_meta": [{"round": 0, "tool": "office_generate", "arguments": {"query": "生成"}}],
        "tool_calls_rounds": 1,
        "tool_call_path": "native",
        "awaiting_confirmation": True,
        "confirmation_token": "tok-1",
        "draft": {"summary": "将生成文档"},
    }

    with patch.object(orch, "_run_tool_calls_rounds",
                      return_value=("请确认以下操作", {}, confirm_meta, [])):
        events = list(orch.process_stream("生成请假单", [], ctx, use_native_tool_calls=True))

    data_blob = "\n".join(events)
    assert "awaiting_confirmation" in data_blob
    assert "tok-1" in data_blob
    assert 'finish_reason": "stop"' not in data_blob  # 确认场景不落 done(stop)
