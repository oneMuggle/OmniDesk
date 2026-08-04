"""orchestrator.process confirm 拦截单元测试(confirm-replay 框架 Phase B)。

覆盖:
- require_confirmation=False 工具 → 不拦截,走既有路径
- require_confirmation=True + 无 hook → 直接执行(apply_pre_execute_hooks 透传)
- require_confirmation=True + Reject(confirmation_required) + dry_run 返回 draft → awaiting_confirmation
- require_confirmation=True + Reject + dry_run 未返回 draft → 错误
- require_confirmation=True + Reject(其他 error_code) → 不拦截,走既有路径
- require_confirmation=True + pre-hook 返回 dict → 不拦截,走既有路径
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
        assert result["tool_result"]["draft"]["summary"] == "将执行测试操作"
        assert result["error"] is False
        # 不走 LLM 合成 → answer = draft.summary
        assert result["answer"] == "将执行测试操作"

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
    def test_pre_hook_reject_other_error_code_not_intercepted(
        self, mock_generate, mock_chain_plan, mock_classify, tool_context
    ):
        """require_confirmation=True + Reject(其他 error_code) → 不拦截,走既有路径"""
        mock_classify.return_value = "write_confirm_intent"
        mock_chain_plan.return_value = []
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
        ):
            result = AgentOrchestrator().process("test", tool_context=tool_context)

        # 不拦截,走既有路径
        assert result.get("awaiting_confirmation") is not True
        assert result["answer"] == "written"

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
