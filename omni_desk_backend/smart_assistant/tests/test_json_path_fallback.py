"""JSON fallback 路径的路由与业务对等性测试。"""
from unittest.mock import MagicMock, patch

import pytest

from smart_assistant.agent.orchestrator import AgentOrchestrator
from smart_assistant.tools.tool_context import ToolContext


@pytest.fixture
def mock_context():
    user = MagicMock(is_authenticated=True, is_staff=False)
    return ToolContext(user=user)


@pytest.fixture
def orchestrator():
    instance = AgentOrchestrator()
    instance.router = MagicMock()
    return instance


@pytest.mark.django_db
def test_process_falls_back_to_json_when_setting_disabled(
    orchestrator, mock_context, settings
):
    """settings 关闭时强制走 JSON 路径。"""
    settings.USE_NATIVE_TOOL_CALLS = False
    with patch.object(
        orchestrator, "_endpoint_supports_tool_calls", return_value=True
    ), patch.object(
        orchestrator,
        "_process_json_path",
        return_value=("ok", {}, {"tool_call_path": "json"}),
    ) as mock_json, patch.object(orchestrator, "_process_tool_calls_path") as mock_native:
        result = orchestrator.process(query="x", tool_context=mock_context)

    mock_json.assert_called_once()
    mock_native.assert_not_called()
    assert result["answer"] == "ok"
    assert result["tool_call_path"] == "json"


@pytest.mark.django_db
def test_process_falls_back_when_endpoint_lacks_capability(
    orchestrator, mock_context, settings
):
    """端点 capability=false 时走 JSON 路径。"""
    settings.USE_NATIVE_TOOL_CALLS = True
    with patch.object(
        orchestrator, "_endpoint_supports_tool_calls", return_value=False
    ), patch.object(
        orchestrator,
        "_process_json_path",
        return_value=("ok", {}, {"tool_call_path": "json"}),
    ) as mock_json, patch.object(orchestrator, "_process_tool_calls_path") as mock_native:
        result = orchestrator.process(query="x", tool_context=mock_context)

    mock_json.assert_called_once()
    mock_native.assert_not_called()
    assert result["tool_call_path"] == "json"


@pytest.mark.django_db
def test_json_path_result_matches_legacy_result_key_fields(
    orchestrator, mock_context
):
    """JSON 路径包装结果与 legacy dict 在关键业务字段上严格一致。"""
    legacy_result = {
        "answer": "需要确认",
        "intent": "swap_request",
        "tool_used": "swap_request",
        "tool_result": {"draft": {"from": "A", "to": "B"}},
        "sources": [{"title": "内部制度"}],
        "usage": {"total_tokens": 12},
        "tool_fallback": False,
        "tool_chain": [],
        "awaiting_confirmation": True,
        "confirmation_token": "token-123",
        "error": False,
    }
    key_fields = (
        "answer",
        "intent",
        "tool_used",
        "tool_result",
        "sources",
        "tool_fallback",
        "tool_chain",
        "awaiting_confirmation",
        "confirmation_token",
        "tool_call_path",
    )

    with patch.object(orchestrator, "_legacy_process", return_value=legacy_result) as mock_legacy:
        json_result = orchestrator.process(query="请调班", tool_context=mock_context)

    mock_legacy.assert_called_once_with("请调班", None, mock_context)
    expected = {**legacy_result, "tool_call_path": "json"}
    assert {field: json_result.get(field) for field in key_fields} == {
        field: expected.get(field) for field in key_fields
    }


@pytest.mark.django_db
def test_process_json_path_meta_three_tuple_has_path_json(
    orchestrator, mock_context
):
    """_process_json_path 返回三元组时，meta 明确标记 JSON 路径。"""
    legacy_result = {
        "answer": "普通回答",
        "usage": {"total_tokens": 3},
        "intent": "general_chat",
        "tool_used": None,
        "tool_result": None,
        "sources": [],
        "tool_fallback": False,
        "tool_chain": None,
        "awaiting_confirmation": False,
        "confirmation_token": None,
    }
    with patch.object(orchestrator, "_legacy_process", return_value=legacy_result):
        content, usage, meta = orchestrator._process_json_path(
            query="你好", context=mock_context, llm_messages=None
        )

    assert content == legacy_result["answer"]
    assert usage == legacy_result["usage"]
    assert meta["tool_call_path"] == "json"
