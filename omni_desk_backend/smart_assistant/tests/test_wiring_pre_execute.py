"""apply_pre_execute_hooks 单元测试(confirm-replay 框架 Phase A)。

覆盖:
- 无 pre hook 时走快速路径,直接返回 params
- pre hook 修改 params → 返回修改后的 params
- pre hook 返回 Reject(confirmation_required) → 返回 Reject,上层识别
- pre hook 抛异常 → 降级返回原 params(失败安全)
- pre hook 链优先级:priority 大的先执行
- Reject 短路:第二个 hook 不再被调用
"""

import pytest

from smart_assistant.hooks.base import (
    HookEvent,
    Reject,
    ToolHookBase,
    get_registry,
)
from smart_assistant.hooks.wiring import apply_pre_execute_hooks


@pytest.fixture(autouse=True)
def _clean_registry():
    """每个测试前清空全局注册表,测试后恢复。"""
    registry = get_registry(reset=True)
    yield registry
    get_registry(reset=True)


class _PassthroughTool:
    """mock 工具:仅 name 属性,apply_pre_execute_hooks 只读 name。"""

    name = "mock_tool"


class _MockCtx:
    """mock 上下文:apply_pre_execute_hooks 透传给 hook,本身不解释。"""

    user = None


@pytest.mark.django_db
class TestApplyPreExecuteHooksFastPath:
    """无 hook 时的快速路径。"""

    def test_no_pre_hook_returns_params_unchanged(self):
        """注册表空 → 直接返回 params,不调任何 hook"""
        params = {"query": "test"}
        result = apply_pre_execute_hooks(_PassthroughTool(), _MockCtx(), params)

        assert result == params

    def test_empty_dict_params_returns_empty(self):
        """空 dict params 也走快速路径"""
        assert apply_pre_execute_hooks(_PassthroughTool(), _MockCtx(), {}) == {}


@pytest.mark.django_db
class TestApplyPreExecuteHooksModify:
    """hook 修改 params 的场景。"""

    def test_hook_modifies_params(self):
        """pre hook 注入字段 → 返回修改后的 params"""

        class InjectHook(ToolHookBase):
            name = "injector"

            async def pre_execute(self, tool, ctx, params):
                return {**params, "injected": True}

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, InjectHook(), priority=10)

        result = apply_pre_execute_hooks(
            _PassthroughTool(), _MockCtx(), {"query": "test"}
        )

        assert result == {"query": "test", "injected": True}

    def test_hook_chain_priority(self):
        """高优先级 hook 先执行,其输出作为下一个 hook 的输入"""

        class HookA(ToolHookBase):
            name = "hook_a"

            async def pre_execute(self, tool, ctx, params):
                return {**params, "order": params.get("order", []) + ["A"]}

        class HookB(ToolHookBase):
            name = "hook_b"

            async def pre_execute(self, tool, ctx, params):
                return {**params, "order": params.get("order", []) + ["B"]}

        registry = get_registry()
        # B 优先级高 → 先执行 → 输出传给 A
        registry.register(HookEvent.PRE_EXECUTE, HookA(), priority=5)
        registry.register(HookEvent.PRE_EXECUTE, HookB(), priority=10)

        result = apply_pre_execute_hooks(
            _PassthroughTool(), _MockCtx(), {"order": []}
        )

        assert result["order"] == ["B", "A"]


@pytest.mark.django_db
class TestApplyPreExecuteHooksReject:
    """hook 返回 Reject 的场景(确认流程核心)。"""

    def test_reject_confirmation_required(self):
        """hook 返回 Reject(error_code=confirmation_required) → 返回 Reject"""

        class ConfirmGuardHook(ToolHookBase):
            name = "confirm_guard"

            async def pre_execute(self, tool, ctx, params):
                return Reject(
                    reason="工具 require_confirmation=True",
                    should_abort=True,
                    error_code="confirmation_required",
                )

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, ConfirmGuardHook(), priority=10)

        result = apply_pre_execute_hooks(
            _PassthroughTool(), _MockCtx(), {"query": "test"}
        )

        assert isinstance(result, Reject)
        assert result.error_code == "confirmation_required"
        assert result.should_abort is True

    def test_reject_short_circuits_chain(self):
        """第一个 hook 返回 Reject → 后续 hook 不再执行"""
        call_log = []

        class FirstRejectHook(ToolHookBase):
            name = "first_reject"

            async def pre_execute(self, tool, ctx, params):
                call_log.append("first")
                return Reject(reason="stop here", error_code="confirmation_required")

        class NeverReachedHook(ToolHookBase):
            name = "never_reached"

            async def pre_execute(self, tool, ctx, params):
                call_log.append("second")
                return params

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, FirstRejectHook(), priority=10)
        registry.register(HookEvent.PRE_EXECUTE, NeverReachedHook(), priority=5)

        result = apply_pre_execute_hooks(
            _PassthroughTool(), _MockCtx(), {"query": "test"}
        )

        assert isinstance(result, Reject)
        assert call_log == ["first"]  # 第二个 hook 没被调用


@pytest.mark.django_db
class TestApplyPreExecuteHooksDegradation:
    """失败降级场景。"""

    def test_hook_exception_degrades_to_params(self):
        """hook 抛异常 → 降级返回原 params,不影响主流程"""

        class BrokenHook(ToolHookBase):
            name = "broken"

            async def pre_execute(self, tool, ctx, params):
                raise RuntimeError("钩子内部出错")

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, BrokenHook(), priority=10)

        params = {"query": "test"}
        result = apply_pre_execute_hooks(_PassthroughTool(), _MockCtx(), params)

        assert result == params  # 降级透传

    def test_hook_returns_wrong_type_degrades(self):
        """hook 返回非 dict/Reject(如 int) → 防御降级为原 params"""

        class BadReturnHook(ToolHookBase):
            name = "bad_return"

            async def pre_execute(self, tool, ctx, params):
                return 42  # 类型错误

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, BadReturnHook(), priority=10)

        params = {"query": "test"}
        result = apply_pre_execute_hooks(_PassthroughTool(), _MockCtx(), params)

        # 防御逻辑:非 dict/Reject 时降级
        assert result == params

    def test_reject_without_error_code(self):
        """hook 返回 Reject 但 error_code=None → 仍然返回 Reject(上层自行判定)"""

        class GenericRejectHook(ToolHookBase):
            name = "generic_reject"

            async def pre_execute(self, tool, ctx, params):
                return Reject(reason="权限不足", error_code=None)

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, GenericRejectHook(), priority=10)

        result = apply_pre_execute_hooks(
            _PassthroughTool(), _MockCtx(), {"query": "test"}
        )

        assert isinstance(result, Reject)
        assert result.error_code is None
        assert result.reason == "权限不足"
