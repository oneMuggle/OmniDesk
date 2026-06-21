"""Hook 系统单元测试

覆盖 hooks/base.py 的所有公开接口:
- HookEvent 枚举
- Reject / RecoveryAction / HookResult dataclass
- ToolHook Protocol
- HookRegistry 注册/注销/执行/优先级/异常隔离
- get_registry() 单例行为
"""

import asyncio

import pytest

from smart_assistant.hooks.base import (
    HookEvent,
    HookRegistry,
    HookResult,
    RecoveryAction,
    Reject,
    ToolHook,
    ToolHookBase,
    get_registry,
)


# ---------------------------------------------------------------------------
# 测试用的 Mock Hook 实现
# ---------------------------------------------------------------------------


class PassthroughHook(ToolHookBase):
    """默认放行的 Hook(使用基类的默认方法)"""

    name = "passthrough"


class ModifyingPreHook(ToolHookBase):
    """修改输入参数的 Hook"""

    name = "modifying_pre"

    async def pre_execute(self, tool, ctx, params):
        return {**params, "modified_by": self.name}


class RejectingHook(ToolHookBase):
    """拒绝执行的 Hook"""

    name = "rejecting"

    def __init__(self, reason="拒绝原因", should_abort=False):
        self._reason = reason
        self._should_abort = should_abort

    async def pre_execute(self, tool, ctx, params):
        return Reject(reason=self._reason, should_abort=self._should_abort)


class ModifyingPostHook(ToolHookBase):
    """修改输出结果的 Hook"""

    name = "modifying_post"

    async def post_execute(self, tool, result, ctx):
        return {**result, "post_modified": True} if isinstance(result, dict) else result


class FailingHook(ToolHookBase):
    """Hook 自身抛出异常"""

    name = "failing"

    async def pre_execute(self, tool, ctx, params):
        raise RuntimeError("Hook 自身错误")


class RecoveryHook(ToolHookBase):
    """返回恢复动作的 Hook"""

    name = "recovery"

    def __init__(self, action="retry"):
        self._action = action

    async def on_failure(self, tool, error, ctx):
        return RecoveryAction(action=self._action, retry_count=1)


# ---------------------------------------------------------------------------
# HookEvent 枚举测试
# ---------------------------------------------------------------------------


class TestHookEvent:
    def test_all_events_defined(self):
        """验证所有 3 种事件都已定义"""
        assert set(HookEvent) == {
            HookEvent.PRE_EXECUTE,
            HookEvent.POST_EXECUTE,
            HookEvent.ON_FAILURE,
        }

    def test_event_values(self):
        """验证事件值是小写字符串"""
        assert HookEvent.PRE_EXECUTE.value == "pre_execute"
        assert HookEvent.POST_EXECUTE.value == "post_execute"
        assert HookEvent.ON_FAILURE.value == "on_failure"


# ---------------------------------------------------------------------------
# Dataclass 测试
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_reject_fields(self):
        """Reject 包含必需字段"""
        r = Reject(reason="test")
        assert r.reason == "test"
        assert r.should_abort is False
        assert r.error_code is None

    def test_reject_frozen(self):
        """Reject 是 frozen dataclass"""
        r = Reject(reason="test")
        with pytest.raises(AttributeError):
            r.reason = "new"  # type: ignore[misc]

    def test_recovery_action_defaults(self):
        """RecoveryAction 默认字段"""
        a = RecoveryAction(action="retry")
        assert a.new_params is None
        assert a.fallback_value is None
        assert a.retry_count == 0

    def test_hook_result_payload_default(self):
        """HookResult 的 payload 默认为空 dict"""
        r = HookResult(hook_name="test", event=HookEvent.PRE_EXECUTE, outcome="allowed")
        assert r.payload == {}


# ---------------------------------------------------------------------------
# ToolHook Protocol 测试
# ---------------------------------------------------------------------------


class TestToolHookProtocol:
    def test_passthrough_hook_is_tool_hook(self):
        """PassthroughHook 符合 ToolHook Protocol"""
        hook = PassthroughHook()
        assert isinstance(hook, ToolHook)

    def test_rejecting_hook_is_tool_hook(self):
        """RejectingHook 符合 ToolHook Protocol"""
        hook = RejectingHook()
        assert isinstance(hook, ToolHook)

    def test_non_conforming_object_not_tool_hook(self):
        """不符合 Protocol 的对象不被识别"""

        class BadHook:
            """缺少 name 属性"""

            async def pre_execute(self, tool, ctx, params):
                return params

        assert not isinstance(BadHook(), ToolHook)


# ---------------------------------------------------------------------------
# HookRegistry 注册/注销测试
# ---------------------------------------------------------------------------


class TestHookRegistryRegistration:
    def setup_method(self):
        """每个测试方法前清空 registry"""
        self.registry = HookRegistry()

    def test_register_single_hook(self):
        """注册单个 Hook"""
        hook = PassthroughHook()
        self.registry.register(HookEvent.PRE_EXECUTE, hook)
        assert hook in self.registry.list_hooks(HookEvent.PRE_EXECUTE)

    def test_register_hook_to_multiple_events(self):
        """同一 Hook 可注册到多个事件"""
        hook = PassthroughHook()
        self.registry.register(HookEvent.PRE_EXECUTE, hook)
        self.registry.register(HookEvent.POST_EXECUTE, hook)
        assert hook in self.registry.list_hooks(HookEvent.PRE_EXECUTE)
        assert hook in self.registry.list_hooks(HookEvent.POST_EXECUTE)

    def test_register_duplicate_is_noop(self):
        """重复注册不重复"""
        hook = PassthroughHook()
        self.registry.register(HookEvent.PRE_EXECUTE, hook)
        self.registry.register(HookEvent.PRE_EXECUTE, hook)
        assert self.registry.list_hooks(HookEvent.PRE_EXECUTE).count(hook) == 1

    def test_register_non_protocol_hook_raises(self):
        """注册不符合 Protocol 的 Hook 抛出 ValueError"""

        class BadHook:
            pass

        with pytest.raises(ValueError, match="不符合 ToolHook Protocol"):
            self.registry.register(HookEvent.PRE_EXECUTE, BadHook())  # type: ignore

    def test_unregister_hook(self):
        """注销 Hook 后不再列出"""
        hook = PassthroughHook()
        self.registry.register(HookEvent.PRE_EXECUTE, hook)
        self.registry.unregister(hook)
        assert hook not in self.registry.list_hooks(HookEvent.PRE_EXECUTE)

    def test_list_hooks_all_events(self):
        """list_hooks(None) 列出所有事件的所有 Hook(去重)"""
        h1 = PassthroughHook()
        h2 = ModifyingPreHook()
        self.registry.register(HookEvent.PRE_EXECUTE, h1)
        self.registry.register(HookEvent.POST_EXECUTE, h2)
        all_hooks = self.registry.list_hooks()
        assert h1 in all_hooks
        assert h2 in all_hooks
        assert len(all_hooks) == 2


# ---------------------------------------------------------------------------
# HookRegistry 优先级排序测试
# ---------------------------------------------------------------------------


class TestHookRegistryPriority:
    def setup_method(self):
        self.registry = HookRegistry()

    def test_higher_priority_first(self):
        """优先级高的 Hook 先执行"""
        low = PassthroughHook()
        low.name = "low"
        high = ModifyingPreHook()
        high.name = "high"
        self.registry.register(HookEvent.PRE_EXECUTE, low, priority=1)
        self.registry.register(HookEvent.PRE_EXECUTE, high, priority=10)
        hooks = self.registry.list_hooks(HookEvent.PRE_EXECUTE)
        assert hooks[0].name == "high"
        assert hooks[1].name == "low"


# ---------------------------------------------------------------------------
# HookRegistry 执行测试(异步)
# ---------------------------------------------------------------------------


class TestHookRegistryExecution:
    def setup_method(self):
        self.registry = HookRegistry()

    def test_run_pre_hooks_no_hooks(self):
        """无 Hook 时,参数原样返回"""
        result = asyncio.run(self.registry.run_pre_hooks(None, None, {"a": 1}))
        assert result == {"a": 1}

    def test_run_pre_hooks_passthrough(self):
        """PassthroughHook 不修改参数"""
        self.registry.register(HookEvent.PRE_EXECUTE, PassthroughHook())
        result = asyncio.run(self.registry.run_pre_hooks(None, None, {"a": 1}))
        assert result == {"a": 1}

    def test_run_pre_hooks_modifies_params(self):
        """ModifyingPreHook 修改参数"""
        self.registry.register(HookEvent.PRE_EXECUTE, ModifyingPreHook())
        result = asyncio.run(self.registry.run_pre_hooks(None, None, {"a": 1}))
        assert result == {"a": 1, "modified_by": "modifying_pre"}

    def test_run_pre_hooks_chain(self):
        """多个 Hook 链式执行,前一个的输出作为后一个的输入"""
        h1 = ModifyingPreHook()
        h1.name = "h1"

        class SecondHook(ToolHookBase):
            name = "h2"

            async def pre_execute(self, tool, ctx, params):
                return {**params, "chained": True}

        self.registry.register(HookEvent.PRE_EXECUTE, h1, priority=10)
        self.registry.register(HookEvent.PRE_EXECUTE, SecondHook(), priority=5)
        result = asyncio.run(self.registry.run_pre_hooks(None, None, {"a": 1}))
        assert result["modified_by"] == "h1"
        assert result["chained"] is True

    def test_run_pre_hooks_reject_short_circuits(self):
        """Reject 立即终止,后续 Hook 不执行"""

        class AfterReject(ToolHookBase):
            name = "after"

            async def pre_execute(self, tool, ctx, params):
                raise AssertionError("不应执行到这里")

        self.registry.register(HookEvent.PRE_EXECUTE, RejectingHook(reason="拒绝"), priority=10)
        self.registry.register(HookEvent.PRE_EXECUTE, AfterReject(), priority=5)
        result = asyncio.run(self.registry.run_pre_hooks(None, None, {"a": 1}))
        assert isinstance(result, Reject)
        assert result.reason == "拒绝"

    def test_run_post_hooks_modifies_result(self):
        """ModifyingPostHook 修改结果"""
        self.registry.register(HookEvent.POST_EXECUTE, ModifyingPostHook())
        result = asyncio.run(self.registry.run_post_hooks(None, {"data": "test"}, None))
        assert result == {"data": "test", "post_modified": True}

    def test_run_failure_hooks_first_non_ignore_wins(self):
        """第一个非 ignore 的 RecoveryAction 返回"""
        ignore_hook = RecoveryHook(action="ignore")
        retry_hook = RecoveryHook(action="retry")
        fallback_hook = RecoveryHook(action="fallback")

        self.registry.register(HookEvent.ON_FAILURE, ignore_hook, priority=10)
        self.registry.register(HookEvent.ON_FAILURE, retry_hook, priority=5)
        self.registry.register(HookEvent.ON_FAILURE, fallback_hook, priority=1)

        result = asyncio.run(self.registry.run_failure_hooks(None, None, Exception("test")))
        assert result.action == "retry"  # 第一个非 ignore 的

    def test_run_failure_hooks_all_ignore(self):
        """所有 Hook 都返回 ignore,默认返回 ignore"""
        self.registry.register(HookEvent.ON_FAILURE, RecoveryHook(action="ignore"))
        result = asyncio.run(self.registry.run_failure_hooks(None, None, Exception("test")))
        assert result.action == "ignore"

    def test_hook_exception_isolation_pre(self):
        """Hook 自身异常不影响主流程"""
        self.registry.register(HookEvent.PRE_EXECUTE, FailingHook(), priority=10)
        self.registry.register(HookEvent.PRE_EXECUTE, ModifyingPreHook(), priority=5)
        result = asyncio.run(self.registry.run_pre_hooks(None, None, {"a": 1}))
        # FailingHook 出错被跳过,ModifyingPreHook 正常执行
        assert result == {"a": 1, "modified_by": "modifying_pre"}

    def test_hook_exception_isolation_post(self):
        """POST_EXECUTE Hook 异常不影响后续 Hook"""

        class FailingPost(ToolHookBase):
            name = "failing_post"

            async def post_execute(self, tool, result, ctx):
                raise RuntimeError("post hook error")

        self.registry.register(HookEvent.POST_EXECUTE, FailingPost(), priority=10)
        self.registry.register(HookEvent.POST_EXECUTE, ModifyingPostHook(), priority=5)
        result = asyncio.run(self.registry.run_post_hooks(None, {"data": "test"}, None))
        # FailingPost 出错被跳过,ModifyingPostHook 正常执行
        assert result == {"data": "test", "post_modified": True}

    def test_recent_results_tracked(self):
        """Hook 执行结果被追踪"""
        self.registry.register(HookEvent.PRE_EXECUTE, PassthroughHook())
        asyncio.run(self.registry.run_pre_hooks(None, None, {"a": 1}))
        results = self.registry.get_recent_results()
        assert len(results) == 1
        assert results[0].hook_name == "passthrough"
        assert results[0].event == HookEvent.PRE_EXECUTE
        assert results[0].outcome == "allowed"

    def test_recent_results_limited_to_100(self):
        """最多保留 100 条结果"""
        for _ in range(150):
            self.registry._record_result(PassthroughHook(), HookEvent.PRE_EXECUTE, "allowed")
        assert len(self.registry.get_recent_results(limit=200)) == 100

    def test_clear_resets_state(self):
        """clear() 清空所有 Hook 和结果"""
        self.registry.register(HookEvent.PRE_EXECUTE, PassthroughHook())
        asyncio.run(self.registry.run_pre_hooks(None, None, {"a": 1}))
        self.registry.clear()
        assert self.registry.list_hooks() == []
        assert self.registry.get_recent_results() == []


# ---------------------------------------------------------------------------
# get_registry() 单例测试
# ---------------------------------------------------------------------------


class TestGetRegistry:
    def setup_method(self):
        """每个测试前重置单例,避免测试间污染"""
        get_registry(reset=True)

    def teardown_method(self):
        get_registry(reset=True)

    def test_returns_same_instance(self):
        """多次调用返回同一实例"""
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_reset_creates_new_instance(self):
        """reset=True 创建新实例"""
        r1 = get_registry()
        r2 = get_registry(reset=True)
        assert r1 is not r2

    def test_singleton_is_hook_registry(self):
        """单例是 HookRegistry 类型"""
        r = get_registry()
        assert isinstance(r, HookRegistry)
