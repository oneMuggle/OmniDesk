"""orchestrator.process confirm 拦截单元测试(confirm-replay 框架 Phase B)。

覆盖:
- require_confirmation=False 工具 → 不拦截,走既有路径
- require_confirmation=True + 无 hook → 直接执行(apply_pre_execute_hooks 透传)
- require_confirmation=True + Reject(confirmation_required) + dry_run 返回 draft → awaiting_confirmation
- require_confirmation=True + Reject + dry_run 未返回 draft → 错误
- require_confirmation=True + Reject(其他 error_code) → P1A-2 enforcement:阻断工具执行,返回 error_code dict
- require_confirmation=True + pre-hook 返回 dict → 不拦截,走既有路径

Task 10 (process_stream 流式拦截):
- require_confirmation=True + Reject(confirmation_required) → SSE 流发出 confirmation 事件,不会直接执行
"""

from unittest.mock import MagicMock, patch

import pytest

from smart_assistant.agent.orchestrator import AgentOrchestrator
from smart_assistant.hooks.base import HookEvent, Reject, ToolHookBase, get_registry
from smart_assistant.tools.base import BaseTool
from smart_assistant.tools.tool_context import ToolContext


# ---------------------------------------------------------------------------
# Mock 工具
# ---------------------------------------------------------------------------


class _ReadOnlyTool(BaseTool):
    """require_confirmation=False(默认)的 read 工具"""

    name = "read_only_tool"
    description = "只读工具"
    intent_type = "read_intent"
    risk_level = "read"

    def execute(self, query=None, context=None, **kwargs):
        return {"found": True, "data": "test"}


class _WriteToolNoConfirmation(BaseTool):
    """require_confirmation 未显式声明的 write 工具(默认 False)"""

    name = "write_no_confirm"
    description = "写工具,未声明 require_confirmation"
    intent_type = "write_intent"
    risk_level = "write"

    def execute(self, query=None, context=None, **kwargs):
        return {"found": True, "result": "written"}


class _WriteToolWithConfirmation(BaseTool):
    """require_confirmation=True 的 write 工具"""

    name = "write_with_confirm"
    description = "写工具,需要二次确认"
    intent_type = "write_confirm_intent"
    risk_level = "write"
    require_confirmation = True

    def execute(self, query=None, context=None, **kwargs):
        # 检测 dry_run 模式
        if isinstance(context, dict) and context.get("dry_run"):
            return {
                "found": True,
                "draft": {
                    "summary": "将执行测试操作",
                    "fields": {"query": query},
                },
            }
        return {"found": True, "result": "really_written"}


class _WriteToolConfirmNoDraft(BaseTool):
    """require_confirmation=True 但未实现 dry_run 模式"""

    name = "write_confirm_no_draft"
    description = "写工具,需要确认但未返回 draft"
    intent_type = "write_confirm_no_draft_intent"
    risk_level = "write"
    require_confirmation = True

    def execute(self, query=None, context=None, **kwargs):
        return {"found": True, "result": "written"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """每个测试前清空全局注册表"""
    get_registry(reset=True)
    yield
    get_registry(reset=True)


@pytest.fixture
def mock_user():
    """mock 用户"""
    user = MagicMock()
    user.pk = 1
    user.id = 1
    return user


@pytest.fixture
def tool_context(mock_user):
    """mock ToolContext"""
    ctx = MagicMock(spec=ToolContext)
    ctx.user = mock_user
    ctx.scope = MagicMock()
    ctx.scope.value = "self"
    return ctx


# ---------------------------------------------------------------------------
# 测试:不拦截场景
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNoInterception:
    """不拦截的场景。"""

    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.generate_answer")
    def test_read_only_tool_not_intercepted(
        self, mock_generate, mock_chain_plan, mock_classify, tool_context
    ):
        """require_confirmation=False 工具 → 不拦截,走既有路径"""
        mock_classify.return_value = "read_intent"
        mock_chain_plan.return_value = []  # 单工具路径
        mock_generate.return_value = ("test answer", None)

        # 注册工具
        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_ReadOnlyTool(),
        ):
            result = AgentOrchestrator().process("test", tool_context=tool_context)

        # 没有 awaiting_confirmation 字段
        assert result.get("awaiting_confirmation") is not True
        assert result["answer"] == "test answer"
        assert result["tool_used"] == "read_only_tool"

    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.generate_answer")
    def test_write_tool_without_confirm_flag_not_intercepted(
        self, mock_generate, mock_chain_plan, mock_classify, tool_context
    ):
        """write 工具但未声明 require_confirmation → 不拦截"""
        mock_classify.return_value = "write_intent"
        mock_chain_plan.return_value = []
        mock_generate.return_value = ("written", None)

        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_WriteToolNoConfirmation(),
        ):
            result = AgentOrchestrator().process("test", tool_context=tool_context)

        assert result.get("awaiting_confirmation") is not True
        assert result["answer"] == "written"


# ---------------------------------------------------------------------------
# 测试:拦截场景
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConfirmationInterception:
    """拦截场景。"""

    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    def test_require_confirmation_true_intercepted(
        self, mock_chain_plan, mock_classify, tool_context
    ):
        """require_confirmation=True + 无 hook → 拦截失败(因为没有 Reject),
        但 apply_pre_execute_hooks 透传,工具直接执行"""
        mock_classify.return_value = "write_confirm_intent"
        mock_chain_plan.return_value = []

        # 无 pre hook 注册 → apply_pre_execute_hooks 返回 params(透传),非 Reject
        # → 走既有路径

        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_WriteToolWithConfirmation(),
        ), patch(
            "smart_assistant.agent.orchestrator.generate_answer",
            return_value=("really written", None),
        ):
            result = AgentOrchestrator().process("test", tool_context=tool_context)

        # 无 hook → 不拦截,直接执行
        assert result.get("awaiting_confirmation") is not True
        assert result["answer"] == "really written"

    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    def test_pre_hook_reject_confirmation_required_returns_awaiting(
        self, mock_chain_plan, mock_classify, tool_context
    ):
        """require_confirmation=True + Reject(confirmation_required) + draft → awaiting_confirmation"""
        mock_classify.return_value = "write_confirm_intent"
        mock_chain_plan.return_value = []

        # 注册 pre hook 返回 Reject
        class ConfirmGuardHook(ToolHookBase):
            name = "confirm_guard"

            async def pre_execute(self, tool, ctx, params):
                return Reject(
                    reason="需要二次确认",
                    should_abort=True,
                    error_code="confirmation_required",
                )

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, ConfirmGuardHook(), priority=10)

        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_WriteToolWithConfirmation(),
        ):
            result = AgentOrchestrator().process("test", tool_context=tool_context)

        # 拦截成功,返回 awaiting_confirmation
        assert result["awaiting_confirmation"] is True
        assert result["confirmation_token"]  # 非空
        assert result["tool_used"] == "write_with_confirm"
        assert result["tool_result"]["draft"]["summary"] == "请确认工具操作"
        assert result["error"] is False
        # 不走 LLM 合成 → answer = draft.summary
        assert result["answer"] == "请确认工具操作"

    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    def test_pre_hook_reject_but_tool_no_draft_returns_error(
        self, mock_chain_plan, mock_classify, tool_context
    ):
        """require_confirmation=True + Reject + 工具未返回 draft → 错误"""
        mock_classify.return_value = "write_confirm_no_draft_intent"
        mock_chain_plan.return_value = []

        class ConfirmGuardHook(ToolHookBase):
            name = "confirm_guard_2"

            async def pre_execute(self, tool, ctx, params):
                return Reject(
                    reason="需要二次确认",
                    error_code="confirmation_required",
                )

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, ConfirmGuardHook(), priority=10)

        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_WriteToolConfirmNoDraft(),
        ):
            result = AgentOrchestrator().process("test", tool_context=tool_context)

        # 错误路径
        assert result["error"] is True
        assert result["awaiting_confirmation"] is False
        assert "未返回预演结果" in result["answer"]

    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.generate_answer")
    def test_pre_hook_reject_other_error_code_blocks_tool(
        self, mock_generate, mock_chain_plan, mock_classify, tool_context
    ):
        """P1A-2 enforcement:require_confirmation=True + Reject(其他 error_code)
        → 直接阻断工具执行,不走 LLM 合成;返回 error_code + retry_after。

        行为变化:T5 之前非 confirmation_required 的 Reject 会 fall-through 到
        既有执行路径,P1A-2 enforcement 后 orchestrator 在确认 error_code !=
        confirmation_required 时直接 return error dict,工具不再执行。
        """
        mock_classify.return_value = "write_confirm_intent"
        mock_chain_plan.return_value = []
        # mock_generate 不会被调用(工具被阻断,不走 LLM 合成);保留 mock 仅为
        # 兼容性防御。
        mock_generate.return_value = ("written", None)

        class PermissionDenyHook(ToolHookBase):
            name = "permission_deny"

            async def pre_execute(self, tool, ctx, params):
                return Reject(
                    reason="权限不足",
                    error_code="permission_denied",  # 不是 confirmation_required
                )

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, PermissionDenyHook(), priority=10)

        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_WriteToolWithConfirmation(),
        ), patch(
            "smart_assistant.agent.orchestrator.execute_guarded"
        ) as mock_exec_guarded:
            result = AgentOrchestrator().process("test", tool_context=tool_context)

        # P1A-2 enforcement:工具未执行(LLM 也未被调用),返回 error dict
        assert mock_exec_guarded.call_count == 0
        assert result["error"] is True
        assert result["error_code"] == "permission_denied"
        assert result["answer"] == "权限不足"
        # 不是 confirmation 路径
        assert result.get("awaiting_confirmation") is not True

    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.generate_answer")
    def test_pre_hook_modifies_params_not_intercepted(
        self, mock_generate, mock_chain_plan, mock_classify, tool_context
    ):
        """require_confirmation=True + pre-hook 返回 dict(修改 params) → 不拦截,走既有路径"""
        mock_classify.return_value = "write_confirm_intent"
        mock_chain_plan.return_value = []
        mock_generate.return_value = ("written", None)

        class ModifyParamsHook(ToolHookBase):
            name = "modify_params"

            async def pre_execute(self, tool, ctx, params):
                return {**params, "extra": "value"}

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, ModifyParamsHook(), priority=10)

        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_WriteToolWithConfirmation(),
        ):
            result = AgentOrchestrator().process("test", tool_context=tool_context)

        # 不拦截,走既有路径
        assert result.get("awaiting_confirmation") is not True
        assert result["answer"] == "written"


# ---------------------------------------------------------------------------
# Task 10: process_stream 流式拦截测试
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStreamConfirmationInterception:
    """process_stream 对 require_confirmation 工具的 SSE 流式拦截。"""

    def test_stream_yields_confirmation_event_for_confirm_tool(self):
        """SSE 流式路径对 require_confirmation 工具应发出 confirmation 事件而非直接执行。

        说明:确认拦截发生在 ``apply_pre_execute_hooks`` 返回
        ``Reject(confirmation_required)`` 之后,需要先调 ``_dry_run`` 拿 draft。
        若 ``_dry_run`` 因 LLM 不可用返回 ``found=False`` 无 draft,orchestrator
        会发失败 done,**但仍不会直接执行生成**——测试断言的核心是"未出现
        file_download";若 draft 可得,则会发出 confirmation 事件。
        """
        from unittest.mock import patch

        from smart_assistant.tools.registry import ToolRegistry

        tool = ToolRegistry.get_tool("office_generate")
        assert tool is not None and tool.require_confirmation

        # 注册 pre hook 触发 Reject(confirmation_required),确保拦截路径生效
        class _ConfirmStreamHook(ToolHookBase):
            name = "confirm_stream_hook"

            async def pre_execute(self, tool, ctx, params):
                return Reject(
                    reason="需要二次确认",
                    error_code="confirmation_required",
                )

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, _ConfirmStreamHook(), priority=20)

        # mock classify_intent 直接返回 office_generate,跳过 LLM 调用
        # mock execute_guarded 返回一个包含 draft 的 dry_run_result,模拟工具正常 dry_run
        # (R3-A1 Task 6:流式调用点在 stream_runner 命名空间解析,mock 迁移至此)
        with patch(
            "smart_assistant.agent.stream_runner.classify_intent",
            return_value="office_generate",
        ), patch(
            "smart_assistant.agent.stream_runner.generate_tool_chain_plan",
            return_value=[],
        ), patch(
            "smart_assistant.agent.stream_runner.execute_guarded",
            return_value={
                "found": True,
                "draft": {
                    "summary": "将生成请假单",
                    "fields": {"query": "生成请假单"},
                },
            },
        ) as mock_execute_guarded:
            events = list(AgentOrchestrator().process_stream("生成请假单", [], None))

        assert mock_execute_guarded.call_count == 1

        data_blob = "\n".join(events)
        assert "awaiting_confirmation" in data_blob or "confirmation_token" in data_blob
        # 不应直接执行生成
        assert "file_download" not in data_blob
