"""AgentOrchestrator tool_calls 路径测试(L1 §3.4 主循环)。

覆盖范围:
- happy path(LLM 第一轮调工具,第二轮返回自然语言)
- 3 轮上限兜底(MAX_TOOL_CALLS_ROUNDS=3 后强制 tool_choice="none")
- 工具错误 4 类:invalid_arguments / tool_unavailable_for_user / tool_timeout / execution_failed
- process() 顶层路由(settings.USE_NATIVE_TOOL_CALLS + endpoint capability)
- _process_json_path() 业务行为对等(不修改现有逻辑)
- orchestrator 降级策略:generate_with_tools 异常 → 回退 generate()

TDD 约束:先写失败测试 → 实现 → GREEN。
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from smart_assistant.agent.orchestrator import AgentOrchestrator
from smart_assistant.tools.tool_context import ToolContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user():
    """Mock 已认证用户(required_auth=True 工具可见)。"""
    user = MagicMock(is_authenticated=True, is_staff=False)
    user.is_authenticated = True
    return user


@pytest.fixture
def tool_context(mock_user):
    return ToolContext(user=mock_user)


@pytest.fixture
def mock_tool():
    """模拟一个标准的 BaseTool 实例。"""
    tool = MagicMock()
    tool.name = "schedule_query"
    tool.intent_type = "schedule_query"
    tool.required_auth = True
    tool.risk_level = "read"
    return tool


@pytest.fixture
def openai_tool_schema():
    """返回 get_openai_tools() 会返回的标准 schema。"""
    return [
        {
            "type": "function",
            "function": {
                "name": "schedule_query",
                "description": "查询排班",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }
    ]


def _make_three_tuple(content, usage_dict, tool_calls):
    """构造 generate_with_tools() 三元组。"""
    return (content, usage_dict, tool_calls)


# ---------------------------------------------------------------------------
# Step 1:happy path(LLM 第一轮调工具,第二轮自然语言)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tool_calls_path_executes_tool_and_returns_answer(
    mock_user, tool_context, mock_tool, openai_tool_schema
):
    """happy path:LLM 第一轮返回 tool_calls,工具执行后第二轮返回自然语言。"""
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()  # 注入 mock router

    # 第一轮返回 tool_calls,第二轮返回最终回答
    orchestrator.router.generate_with_tools.side_effect = [
        _make_three_tuple(
            content=None,
            usage_dict={"total_tokens": 100},
            tool_calls=[
                {
                    "id": "call_001",
                    "type": "function",
                    "function": {
                        "name": "schedule_query",
                        "arguments": json.dumps({"query": "明天"}),
                    },
                }
            ],
        ),
        _make_three_tuple(
            content="明天是张三早班",
            usage_dict={"total_tokens": 50},
            tool_calls=[],
        ),
    ]

    with patch(
        "smart_assistant.tools.registry.ToolRegistry.get_tool_for_user",
        return_value=mock_tool,
    ), patch(
        "smart_assistant.tools.registry.ToolRegistry.get_openai_tools",
        return_value=openai_tool_schema,
    ):
        mock_tool.validate_arguments.return_value = {"query": "明天"}
        mock_tool.supports_scope_filter = False
        mock_tool.execute.return_value = {
            "found": True,
            "items": [{"shift": "早班"}],
        }

        content, usage, meta = orchestrator._process_tool_calls_path(
            query="明天排班",
            context=tool_context,
            llm_messages=[{"role": "user", "content": "明天排班"}],
        )

    assert "张三早班" in content
    assert meta["tool_calls_rounds"] == 1
    assert len(meta["tool_calls_meta"]) == 1
    assert meta["tool_calls_meta"][0]["tool"] == "schedule_query"
    assert meta["tool_calls_meta"][0]["round"] == 0
    assert meta["tool_calls_meta"][0]["arguments"] == {"query": "明天"}
    assert "duration_ms" in meta["tool_calls_meta"][0]
    assert meta["tool_call_path"] == "native"
    # generate_with_tools 应被调用 2 次(第一轮 + 第二轮自然语言)
    assert orchestrator.router.generate_with_tools.call_count == 2


# ---------------------------------------------------------------------------
# Step 2:LLM 不调工具 → 直接返回 content
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tool_calls_path_returns_immediately_when_no_tool_calls(
    mock_user, tool_context, openai_tool_schema
):
    """LLM 第一轮即返回自然语言(无 tool_calls)→ 立即返回,不再循环。"""
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()
    orchestrator.router.generate_with_tools.return_value = _make_three_tuple(
        content="直接回答",
        usage_dict={"total_tokens": 30},
        tool_calls=[],
    )

    with patch(
        "smart_assistant.tools.registry.ToolRegistry.get_openai_tools",
        return_value=openai_tool_schema,
    ):
        content, usage, meta = orchestrator._process_tool_calls_path(
            query="hi",
            context=tool_context,
            llm_messages=[{"role": "user", "content": "hi"}],
        )

    assert content == "直接回答"
    assert meta["tool_calls_rounds"] == 0
    assert meta["tool_calls_meta"] == []
    assert meta["tool_call_path"] == "native"
    assert orchestrator.router.generate_with_tools.call_count == 1


# ---------------------------------------------------------------------------
# Step 3:3 轮上限兜底(LLM 永远调工具 → 强制 tool_choice="none")
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tool_calls_path_max_rounds_fallback_to_force_no_tools(
    mock_user, tool_context, mock_tool, openai_tool_schema
):
    """LLM 永远返回 tool_calls → 3 轮后强制 tool_choice="none" → 兜底返回 content。"""
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()

    # 3 轮都返回 tool_calls,第 4 轮(强制 tool_choice="none")返回自然语言
    tool_call_payload = [
        {
            "id": "call_loop",
            "type": "function",
            "function": {
                "name": "schedule_query",
                "arguments": json.dumps({"query": "loop"}),
            },
        }
    ]
    orchestrator.router.generate_with_tools.side_effect = [
        _make_three_tuple("", {"total_tokens": 50}, tool_call_payload),
        _make_three_tuple("", {"total_tokens": 50}, tool_call_payload),
        _make_three_tuple("", {"total_tokens": 50}, tool_call_payload),
        _make_three_tuple("兜底回答", {"total_tokens": 100}, []),
    ]

    with patch(
        "smart_assistant.tools.registry.ToolRegistry.get_tool_for_user",
        return_value=mock_tool,
    ), patch(
        "smart_assistant.tools.registry.ToolRegistry.get_openai_tools",
        return_value=openai_tool_schema,
    ):
        mock_tool.validate_arguments.return_value = {"query": "loop"}
        mock_tool.supports_scope_filter = False
        mock_tool.execute.return_value = {"found": True}

        content, usage, meta = orchestrator._process_tool_calls_path(
            query="loop",
            context=tool_context,
            llm_messages=[{"role": "user", "content": "loop"}],
        )

    assert content == "兜底回答"
    # 实际 tool 调用 3 轮(MAX_TOOL_CALLS_ROUNDS=3)
    assert meta["tool_calls_rounds"] == 3
    # 4 次 generate_with_tools 调用(3 轮循环 + 1 次兜底)
    assert orchestrator.router.generate_with_tools.call_count == 4
    # 第 4 次必须 tool_choice="none"
    final_call_kwargs = orchestrator.router.generate_with_tools.call_args_list[-1].kwargs
    assert final_call_kwargs["tool_choice"] == "none"
    # 第 1-3 次 tool_choice="auto"
    for call in orchestrator.router.generate_with_tools.call_args_list[:3]:
        assert call.kwargs["tool_choice"] == "auto"


# ---------------------------------------------------------------------------
# Step 4:错误 1 - tool_unavailable_for_user(get_tool_for_user 返回 None)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tool_calls_path_tool_unavailable_for_user(
    mock_user, tool_context, openai_tool_schema
):
    """工具对当前用户不可见 → tool message 返回 tool_unavailable_for_user。"""
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()
    orchestrator.router.generate_with_tools.side_effect = [
        _make_three_tuple(
            "",
            {"total_tokens": 100},
            [
                {
                    "id": "call_unauth",
                    "type": "function",
                    "function": {
                        "name": "schedule_query",
                        "arguments": json.dumps({"query": "x"}),
                    },
                }
            ],
        ),
        _make_three_tuple("LLM 重选", {"total_tokens": 50}, []),
    ]

    with patch(
        "smart_assistant.tools.registry.ToolRegistry.get_tool_for_user",
        return_value=None,  # 工具不可用
    ), patch(
        "smart_assistant.tools.registry.ToolRegistry.get_openai_tools",
        return_value=openai_tool_schema,
    ):
        _, _, meta = orchestrator._process_tool_calls_path(
            query="x",
            context=tool_context,
            llm_messages=[{"role": "user", "content": "x"}],
        )

    assert len(meta["tool_calls_meta"]) == 1
    assert meta["tool_calls_meta"][0]["tool"] == "schedule_query"
    assert meta["tool_calls_meta"][0]["error"] == "unavailable"


# ---------------------------------------------------------------------------
# Step 5:错误 2 - invalid_arguments(validate_arguments 抛异常)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tool_calls_path_invalid_arguments(
    mock_user, tool_context, mock_tool, openai_tool_schema
):
    """validate_arguments 抛异常 → 注入 invalid_arguments 错误。"""
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()
    orchestrator.router.generate_with_tools.side_effect = [
        _make_three_tuple(
            "",
            {"total_tokens": 100},
            [
                {
                    "id": "call_bad",
                    "type": "function",
                    "function": {
                        "name": "schedule_query",
                        "arguments": "not-valid-json",
                    },
                }
            ],
        ),
        _make_three_tuple("LLM 重试", {"total_tokens": 50}, []),
    ]

    with patch(
        "smart_assistant.tools.registry.ToolRegistry.get_tool_for_user",
        return_value=mock_tool,
    ), patch(
        "smart_assistant.tools.registry.ToolRegistry.get_openai_tools",
        return_value=openai_tool_schema,
    ):
        # validate_arguments 抛 JSON schema 异常(json.loads 已经失败,根本走不到 validate_arguments)
        # 这里使用合法 JSON 但 validate_arguments 抛错的情况
        mock_tool.validate_arguments.side_effect = Exception("schema invalid")

        _, _, meta = orchestrator._process_tool_calls_path(
            query="x",
            context=tool_context,
            llm_messages=[{"role": "user", "content": "x"}],
        )

    assert len(meta["tool_calls_meta"]) == 1
    assert meta["tool_calls_meta"][0]["error"] == "invalid_args"


# ---------------------------------------------------------------------------
# Step 6:错误 3 - tool_timeout(execute_with_guard 抛 timeout)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tool_calls_path_tool_timeout(
    mock_user, tool_context, mock_tool, openai_tool_schema
):
    """工具执行超时 → 注入 tool_timeout 错误。"""
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()
    orchestrator.router.generate_with_tools.side_effect = [
        _make_three_tuple(
            "",
            {"total_tokens": 100},
            [
                {
                    "id": "call_slow",
                    "type": "function",
                    "function": {
                        "name": "schedule_query",
                        "arguments": json.dumps({"query": "x"}),
                    },
                }
            ],
        ),
        _make_three_tuple("降级回答", {"total_tokens": 50}, []),
    ]

    with patch(
        "smart_assistant.tools.registry.ToolRegistry.get_tool_for_user",
        return_value=mock_tool,
    ), patch(
        "smart_assistant.tools.registry.ToolRegistry.get_openai_tools",
        return_value=openai_tool_schema,
    ):
        mock_tool.validate_arguments.return_value = {"query": "x"}
        mock_tool.supports_scope_filter = False
        # 模拟 timeout 异常(实际由 TimeoutGuardHook 包装后抛)
        mock_tool.execute.side_effect = TimeoutError("tool timeout")

        _, _, meta = orchestrator._process_tool_calls_path(
            query="x",
            context=tool_context,
            llm_messages=[{"role": "user", "content": "x"}],
        )

    assert len(meta["tool_calls_meta"]) == 1
    # 超时归类为 execution_failed(execute_with_guard 抛出的任意异常统一走 execution_failed 分支)
    assert meta["tool_calls_meta"][0]["error"] == "execution_failed"


# ---------------------------------------------------------------------------
# Step 7:错误 4 - execution_failed(任意非超时异常)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tool_calls_path_execution_failed(
    mock_user, tool_context, mock_tool, openai_tool_schema
):
    """工具执行抛通用异常 → 注入 execution_failed。"""
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()
    orchestrator.router.generate_with_tools.side_effect = [
        _make_three_tuple(
            "",
            {"total_tokens": 100},
            [
                {
                    "id": "call_err",
                    "type": "function",
                    "function": {
                        "name": "schedule_query",
                        "arguments": json.dumps({"query": "x"}),
                    },
                }
            ],
        ),
        _make_three_tuple("降级回答", {"total_tokens": 50}, []),
    ]

    with patch(
        "smart_assistant.tools.registry.ToolRegistry.get_tool_for_user",
        return_value=mock_tool,
    ), patch(
        "smart_assistant.tools.registry.ToolRegistry.get_openai_tools",
        return_value=openai_tool_schema,
    ):
        mock_tool.validate_arguments.return_value = {"query": "x"}
        mock_tool.supports_scope_filter = False
        mock_tool.execute.side_effect = RuntimeError("DB connection lost")

        _, _, meta = orchestrator._process_tool_calls_path(
            query="x",
            context=tool_context,
            llm_messages=[{"role": "user", "content": "x"}],
        )

    assert len(meta["tool_calls_meta"]) == 1
    assert meta["tool_calls_meta"][0]["error"] == "execution_failed"


# ---------------------------------------------------------------------------
# Step 8:process() 顶层路由 - USE_NATIVE_TOOL_CALLS=True + endpoint 能力 OK
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_process_routes_to_tool_calls_path_when_capable(settings):
    """settings.USE_NATIVE_TOOL_CALLS=True、endpoint 支持且用户为 staff 时,走 tool_calls 路径。

    L1 灰度(Task 12):USE_NATIVE_TOOL_CALLS_FOR_ALL=False(默认)时,仅
    is_staff=True 用户走原生路径;非 staff 或无用户上下文一律降级到 JSON 路径。
    process() 返回 dict(向后兼容);tuple 由 _process_tool_calls_path() 内部产出。
    """
    settings.USE_NATIVE_TOOL_CALLS = True
    staff_user = MagicMock(is_authenticated=True, is_staff=True)
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()
    orchestrator.router.generate_with_tools.return_value = ("tool_call_path answer", {}, [])

    with patch.object(
        orchestrator, "_endpoint_supports_tool_calls", return_value=True
    ), patch.object(
        orchestrator, "_process_tool_calls_path", return_value=("t", {}, {"tool_call_path": "native"})
    ) as mock_tc, patch.object(
        orchestrator, "_process_json_path", return_value=("j", {}, {"tool_call_path": "json"})
    ) as mock_json:
        result = orchestrator.process(
            query="q", tool_context=ToolContext(user=staff_user)
        )

    assert mock_tc.called
    assert not mock_json.called
    # process() 返回 dict(向后兼容);tool_call_path="native" 表明走了 tool_calls 路径
    assert isinstance(result, dict)
    assert result["answer"] == "t"
    assert result["tool_call_path"] == "native"


@pytest.mark.django_db
def test_non_staff_falls_back_to_json_path(settings, mock_user):
    """灰度期间非 staff 用户走 JSON 路径(即 test_process_routes_to_tool_calls_path_when_capable 的对照组)。

    USE_NATIVE_TOOL_CALLS=True + endpoint 支持,但 USE_NATIVE_TOOL_CALLS_FOR_ALL=False
    且用户 is_staff=False → 强制降级到 JSON 路径。
    """
    settings.USE_NATIVE_TOOL_CALLS = True
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()

    with patch.object(
        orchestrator, "_endpoint_supports_tool_calls", return_value=True
    ), patch.object(
        orchestrator, "_process_tool_calls_path", return_value=("t", {}, {"tool_call_path": "native"})
    ) as mock_tc, patch.object(
        orchestrator, "_process_json_path", return_value=("j", {}, {"tool_call_path": "json"})
    ) as mock_json:
        result = orchestrator.process(
            query="q", tool_context=ToolContext(user=mock_user)
        )

    assert mock_json.called
    assert not mock_tc.called
    assert result["tool_call_path"] == "json"


@pytest.mark.django_db
def test_process_routes_to_json_when_no_user_context(settings):
    """灰度期间无用户上下文(内部调用)也走 JSON 路径,更保守。

    等价于 Task 6 时期 `process(query="q")` 不带 tool_context 的调用:
    灰度门控把它视为非 staff → JSON,避免实验路径暴露给未知身份。
    """
    settings.USE_NATIVE_TOOL_CALLS = True
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()

    with patch.object(
        orchestrator, "_endpoint_supports_tool_calls", return_value=True
    ), patch.object(
        orchestrator, "_process_tool_calls_path", return_value=("t", {}, {"tool_call_path": "native"})
    ) as mock_tc, patch.object(
        orchestrator, "_process_json_path", return_value=("j", {}, {"tool_call_path": "json"})
    ) as mock_json:
        result = orchestrator.process(query="q")

    assert mock_json.called
    assert not mock_tc.called
    assert result["tool_call_path"] == "json"


@pytest.mark.django_db
def test_process_routes_to_native_when_for_all_enabled(settings, mock_user):
    """USE_NATIVE_TOOL_CALLS_FOR_ALL=True 时非 staff 用户也走原生路径(全员开放)。"""
    settings.USE_NATIVE_TOOL_CALLS = True
    settings.USE_NATIVE_TOOL_CALLS_FOR_ALL = True
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()
    orchestrator.router.generate_with_tools.return_value = ("tool_call_path answer", {}, [])

    with patch.object(
        orchestrator, "_endpoint_supports_tool_calls", return_value=True
    ), patch.object(
        orchestrator, "_process_tool_calls_path", return_value=("t", {}, {"tool_call_path": "native"})
    ) as mock_tc, patch.object(
        orchestrator, "_process_json_path", return_value=("j", {}, {"tool_call_path": "json"})
    ) as mock_json:
        result = orchestrator.process(
            query="q", tool_context=ToolContext(user=mock_user)
        )

    assert mock_tc.called
    assert not mock_json.called
    assert result["tool_call_path"] == "native"


# ---------------------------------------------------------------------------
# Step 9:process() 顶层路由 - USE_NATIVE_TOOL_CALLS=False → JSON 路径
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_process_routes_to_json_path_when_setting_disabled(settings, mock_user):
    """settings.USE_NATIVE_TOOL_CALLS=False → 强制走 JSON 路径。"""
    settings.USE_NATIVE_TOOL_CALLS = False
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()

    with patch.object(
        orchestrator, "_endpoint_supports_tool_calls", return_value=True
    ), patch.object(
        orchestrator, "_process_json_path", return_value=("j", {}, {})
    ) as mock_json, patch.object(
        orchestrator, "_process_tool_calls_path", return_value=("t", {}, {})
    ) as mock_tc:
        orchestrator.process(query="q")

    assert mock_json.called
    assert not mock_tc.called


# ---------------------------------------------------------------------------
# Step 10:process() 顶层路由 - endpoint 不支持 → JSON 路径
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_process_routes_to_json_path_when_endpoint_unsupported(settings, mock_user):
    """endpoint 能力不支持 → 强制走 JSON 路径(即使 USE_NATIVE_TOOL_CALLS=True)。"""
    settings.USE_NATIVE_TOOL_CALLS = True
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()

    with patch.object(
        orchestrator, "_endpoint_supports_tool_calls", return_value=False
    ), patch.object(
        orchestrator, "_process_json_path", return_value=("j", {}, {})
    ) as mock_json, patch.object(
        orchestrator, "_process_tool_calls_path", return_value=("t", {}, {})
    ) as mock_tc:
        orchestrator.process(query="q")

    assert mock_json.called
    assert not mock_tc.called


# ---------------------------------------------------------------------------
# Step 11:_endpoint_supports_tool_calls() 行为
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_endpoint_supports_tool_calls_no_active_endpoint(settings):
    """无激活 endpoint → 返回 False(安全降级)。"""
    orchestrator = AgentOrchestrator()
    assert orchestrator._endpoint_supports_tool_calls() is False


@pytest.mark.django_db
def test_endpoint_supports_tool_calls_with_dict_capability_true(settings):
    """model_capabilities 为 list[dict] 且含 native_tool_calls=True → 返回 True。"""
    from smart_assistant.models import LlmAppConfig, LlmEndpoint

    endpoint = LlmEndpoint.objects.create(
        name="ep",
        api_endpoint="http://test",
        api_key="k",
        is_active=True,
        priority=1,
        model_capabilities=[{"native_tool_calls": True}],
    )
    LlmAppConfig.objects.create(
        app_name="smart_assistant",
        endpoint=endpoint,
        model_name="m",
        is_active=True,
    )
    orchestrator = AgentOrchestrator()
    assert orchestrator._endpoint_supports_tool_calls() is True


@pytest.mark.django_db
def test_endpoint_supports_tool_calls_with_dict_capability_false(settings):
    """model_capabilities 含 native_tool_calls=False → 返回 False。"""
    from smart_assistant.models import LlmAppConfig, LlmEndpoint

    endpoint = LlmEndpoint.objects.create(
        name="ep",
        api_endpoint="http://test",
        api_key="k",
        is_active=True,
        priority=1,
        model_capabilities=[{"native_tool_calls": False}],
    )
    LlmAppConfig.objects.create(
        app_name="smart_assistant",
        endpoint=endpoint,
        model_name="m",
        is_active=True,
    )
    orchestrator = AgentOrchestrator()
    assert orchestrator._endpoint_supports_tool_calls() is False


# ---------------------------------------------------------------------------
# Step 12:降级策略 - generate_with_tools 抛异常 → 回退到 _process_json_path
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tool_calls_path_falls_back_to_json_when_generate_with_tools_raises(
    mock_user, tool_context, openai_tool_schema
):
    """generate_with_tools 抛异常 → orchestrator 应捕获并走 JSON 路径降级(回退)。"""
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()
    # generate_with_tools 抛异常(模拟端点故障)
    orchestrator.router.generate_with_tools.side_effect = RuntimeError("endpoint down")

    with patch.object(
        orchestrator, "_process_json_path", return_value=("j_fallback", {}, {"tool_call_path": "json"})
    ) as mock_json, patch(
        "smart_assistant.tools.registry.ToolRegistry.get_openai_tools",
        return_value=openai_tool_schema,
    ):
        content, usage, meta = orchestrator._process_tool_calls_path(
            query="x",
            context=tool_context,
            llm_messages=[{"role": "user", "content": "x"}],
        )

    # 兜底:回退到 JSON 路径
    assert content == "j_fallback"
    assert meta["tool_call_path"] == "json"
    assert mock_json.called


# ---------------------------------------------------------------------------
# Step 13:_process_json_path 行为对等(不破坏现有业务逻辑)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_process_json_path_returns_meta_with_path_json(settings, mock_user):
    """_process_json_path 应返回 tool_call_path='json' + 空 tool_calls_meta。"""
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()
    orchestrator.router.generate.return_value = ("json answer", {"total_tokens": 10})

    with patch(
        "smart_assistant.agent.orchestrator.classify_intent", return_value="general_chat"
    ), patch(
        "smart_assistant.agent.orchestrator.generate_general_answer", return_value=("json answer", {"total_tokens": 10})
    ), patch(
        "smart_assistant.agent.orchestrator.ToolRegistry.get_tool", return_value=None
    ), patch(
        "smart_assistant.agent.orchestrator.ToolRegistry.get_all_schemas", return_value=[]
    ), patch(
        "smart_assistant.agent.orchestrator.get_cached_intent", return_value=None
    ), patch(
        "smart_assistant.agent.orchestrator.cache_intent"
    ):
        content, usage, meta = orchestrator._process_json_path(
            query="hi",
            context=ToolContext(user=mock_user),
            llm_messages=None,
        )

    assert content == "json answer"
    assert meta["tool_call_path"] == "json"
    assert meta["tool_calls_meta"] == []
    assert meta["tool_calls_rounds"] == 0


# ---------------------------------------------------------------------------
# Step 14:旧 process() 调用方签名兼容性(digest.py / views/chat.py)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_process_legacy_signature_compatible(settings, mock_user):
    """process(query, conversation_history=None, tool_context=None) 旧签名必须仍可调用。"""
    orchestrator = AgentOrchestrator()
    orchestrator.router = MagicMock()
    orchestrator.router.generate.return_value = ("legacy", {"total_tokens": 5})

    with patch(
        "smart_assistant.agent.orchestrator.classify_intent", return_value="general_chat"
    ), patch(
        "smart_assistant.agent.orchestrator.generate_general_answer", return_value=("legacy", {"total_tokens": 5})
    ), patch(
        "smart_assistant.agent.orchestrator.ToolRegistry.get_tool", return_value=None
    ), patch(
        "smart_assistant.agent.orchestrator.ToolRegistry.get_all_schemas", return_value=[]
    ), patch(
        "smart_assistant.agent.orchestrator.get_cached_intent", return_value=None
    ), patch(
        "smart_assistant.agent.orchestrator.cache_intent"
    ):
        # 旧 3 参位置调用(views/chat.py 用的方式)
        result = orchestrator.process(
            "hi",
            conversation_history=None,
            tool_context=ToolContext(user=mock_user),
        )

    assert isinstance(result, dict)
    assert result["answer"] == "legacy"


# ---------------------------------------------------------------------------
# Step 15:F1 回归 — validated dict → query str 拆包契约
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "validated,expected",
    [
        # 优先取 query 字段(所有工具 schema 的必填自然语言输入)
        ({"query": "明天排班"}, "明天排班"),
        # query 存在时,额外结构化字段不污染 query(execute 只消费 query)
        ({"query": "本周", "date_from": "2026-08-03"}, "本周"),
        # 无 query → 序列化非 query 字段,兜底保留 LLM 提供的结构化参数
        ({"date_from": "2026-08-03"}, "date_from: 2026-08-03"),
        ({"date_from": "2026-08-03", "personnel_name": "张三"}, "date_from: 2026-08-03，personnel_name: 张三"),
        # 空 dict / None / str 兜底
        ({}, ""),
        (None, ""),
        ("直接字符串", "直接字符串"),
    ],
)
def test_dict_to_query_conversion(validated, expected):
    """F1 修复:_dict_to_query 把 LLM 参数 dict 拆包为 execute() 期望的 query 字符串。"""
    from smart_assistant.agent.orchestrator import _dict_to_query

    assert _dict_to_query(validated) == expected


@pytest.mark.django_db
def test_all_registered_tools_execute_via_query_string_conversion(settings):
    """F1 回归:全部 19 个已注册工具在原生路径的 dict→str 拆包后都能正确执行。

    此前 orchestrator 把 validated dict 直接传给 execute_with_guard,导致
    memo/document/project/sensor/news/personnel 抛 AttributeError(dict 无
    replace/strip),schedule/event/meeting_room 等把 dict 的 key 当查询词
    静默查错日期。修复后 validated 先经 ``_dict_to_query`` 转成 str 再执行,
    本测试对 ToolRegistry 全部工具逐一验证该契约(不崩溃、返回 dict)。

    注:关闭超时熔断 —— ``TimeoutGuardHook`` 会把工具放进 worker 线程,
    :memory: SQLite 跨连接访问会抛 database table is locked(与 E2E 文件
    的 ``_disable_tool_timeout_guard`` fixture 同理)。
    """
    settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = False

    from smart_assistant.agent.orchestrator import _dict_to_query
    from smart_assistant.tools.registry import ToolRegistry
    from smart_assistant.tools.tool_context import ToolContext

    ctx = ToolContext(user=None)
    failures: list[str] = []
    for tool in ToolRegistry._tools.values():
        try:
            # 所有工具的 OpenAI schema 都以 query 为必填字段
            validated = tool.validate_arguments({"query": "测试"})
            query_str = _dict_to_query(validated)
            assert isinstance(query_str, str), f"{tool.intent_type} 转换结果不是 str"
            result = tool.execute_with_guard(query_str, ctx)
            assert isinstance(result, dict), f"{tool.intent_type} 返回不是 dict"
        except Exception as exc:
            failures.append(f"{tool.intent_type}: {type(exc).__name__}: {exc}")

    assert not failures, "以下工具在原生路径(拆包后)执行失败:\n" + "\n".join(failures)
