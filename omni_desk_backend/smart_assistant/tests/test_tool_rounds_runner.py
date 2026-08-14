"""tool_rounds_runner 轻量冒烟测试(R3-A1 Task 4)。

验证:
- 新模块可导入、orchestrator 保留薄委托方法;
- 主循环行为冒烟:happy path meta 收集 / confirm-replay 提前返回。
"""

import pytest
from unittest.mock import patch

from smart_assistant.agent.tool_rounds_runner import run_tool_calls_rounds


def test_run_tool_calls_rounds_is_importable():
    assert callable(run_tool_calls_rounds)


def test_orchestrator_delegates_run_tool_calls_rounds():
    from smart_assistant.agent.orchestrator import AgentOrchestrator

    assert hasattr(AgentOrchestrator, "_run_tool_calls_rounds")


class _FakeTool:
    name = "schedule_query"
    require_confirmation = False

    @classmethod
    def validate_arguments(cls, args):
        return args


class _FakeCtx:
    user = None


def _make_tool_call(name, args_json, call_id="call_1"):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": args_json},
    }


@pytest.mark.django_db
def test_run_tool_calls_rounds_happy_path_collects_meta():
    """冒烟:一轮工具执行后第二轮返回自然语言,meta 收集正确。"""
    router = _FakeRouter(
        [
            ("", {}, [_make_tool_call("schedule_query", '{"query": "明天"}')]),
            ("排班结果", {"t": 1}, []),
        ]
    )
    messages = []

    with patch(
        "smart_assistant.agent.tool_rounds_runner.ToolRegistry.get_tool_for_user",
        return_value=_FakeTool(),
    ), patch(
        "smart_assistant.agent.tool_rounds_runner.execute_native_tool",
        return_value=({"found": True}, None, None),
    ):
        content, usage, meta, out_messages = run_tool_calls_rounds(
            router,
            query="明天排班",
            context=_FakeCtx(),
            llm_messages=messages,
            json_fallback=lambda **kw: ("fallback", {}, {}),
        )

    assert content == "排班结果"
    assert meta["tool_calls_rounds"] == 1
    assert meta["tool_call_path"] == "native"
    assert len(meta["tool_calls_meta"]) == 1
    assert meta["tool_calls_meta"][0]["tool"] == "schedule_query"
    assert meta["tool_calls_meta"][0]["round"] == 0
    assert meta["tool_calls_meta"][0]["arguments"] == {"query": "明天"}
    assert "duration_ms" in meta["tool_calls_meta"][0]
    # llm_messages 含 assistant(tool_calls) + tool result
    assert out_messages[-1]["role"] == "tool"


@pytest.mark.django_db
def test_run_tool_calls_rounds_confirm_replay_returns_early():
    """冒烟:confirm-replay 提前返回,llm_messages 不含本轮。"""
    confirmation = {"token": "tok-1", "draft": {"summary": "确认删除?"}}
    router = _FakeRouter(
        [
            ("", {}, [_make_tool_call("schedule_query", '{"query": "删除"}')]),
        ]
    )
    messages = []

    with patch(
        "smart_assistant.agent.tool_rounds_runner.ToolRegistry.get_tool_for_user",
        return_value=_FakeTool(),
    ), patch(
        "smart_assistant.agent.tool_rounds_runner.execute_native_tool",
        return_value=({"found": True, "draft": {"summary": "确认删除?"}}, confirmation, None),
    ):
        content, usage, meta, out_messages = run_tool_calls_rounds(
            router,
            query="删除排班",
            context=_FakeCtx(),
            llm_messages=messages,
            json_fallback=lambda **kw: ("fallback", {}, {}),
        )

    assert meta["awaiting_confirmation"] is True
    assert meta["confirmation_token"] == "tok-1"
    assert meta["tool_call_path"] == "native"
    assert content == "确认删除?"
    # confirm 返回时 llm_messages 不含本轮 assistant/tool 消息
    assert out_messages is messages
    assert len(meta["tool_calls_meta"]) == 1
    assert meta["tool_calls_meta"][0]["arguments"] == {"query": "删除"}
    assert "duration_ms" in meta["tool_calls_meta"][0]


class _FakeRouter:
    """按序回放 generate_with_tools 结果的 stub router。"""

    def __init__(self, responses):
        self._responses = list(responses)

    def generate_with_tools(self, *, messages, tools, tool_choice="auto"):
        return self._responses.pop(0)
