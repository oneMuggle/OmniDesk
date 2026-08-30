"""P1A-2: RateLimitHook(写工具速率限制钩子)单元测试。

覆盖 hook 在不同上下文(写工具 / 只读工具 / 跨用户 / 匿名 / ctx 形态)下的行为。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from smart_assistant.hooks.base import Reject
from smart_assistant.hooks.builtin.rate_limit import (
    RateLimitHook,
    _extract_user,
)


def _run(coro):
    """同步驱动 async hook 协程(测试用)。

    与 test_hooks_builtin.py 保持一致使用 asyncio.run:同套件下其他测试
    可能已消费/关闭全局 event loop,get_event_loop() 会抛
    RuntimeError: There is no current event loop。
    """
    return asyncio.run(coro)


class _FakeWriteTool:
    """require_confirmation=True 的假写工具。"""
    name = "swap_request_tool"
    require_confirmation = True


class _FakeReadTool:
    """require_confirmation=False 的假只读工具。"""
    name = "schedule_query_tool"
    require_confirmation = False


@pytest.mark.django_db
class TestRateLimitHook:
    def setup_method(self):
        from django.core.cache import cache
        cache.clear()
        self.hook = RateLimitHook()
        self.hook_increment = RateLimitHook()  # 第二个实例同用同一个 helper

    # --- T2: 只读工具直接放行 ---
    def test_read_tool_bypasses_without_counting(self):
        ctx = SimpleNamespace(user=SimpleNamespace(id=2001, is_authenticated=True))
        result = _run(self.hook.pre_execute(_FakeReadTool(), ctx, {"query": "x"}))
        assert result == {"query": "x"}
        from django.core.cache import cache
        assert cache.get("smart_assistant:write_rate_limit:2001") is None

    # --- T1: 写工具首次调用计数 +1 ---
    def test_write_tool_increments_counter(self):
        ctx = SimpleNamespace(user=SimpleNamespace(id=2002, is_authenticated=True))
        result = _run(self.hook.pre_execute(_FakeWriteTool(), ctx, {"query": "x"}))
        assert result == {"query": "x"}
        from django.core.cache import cache
        assert cache.get("smart_assistant:write_rate_limit:2002") == 1

    # --- T3: 超限返回 Reject ---
    def test_limit_exceeded_returns_reject_with_retry_after(self):
        ctx = SimpleNamespace(user=SimpleNamespace(id=2003, is_authenticated=True))
        # 撑到上限
        for _ in range(10):
            _run(self.hook.pre_execute(_FakeWriteTool(), ctx, {"query": "x"}))
        # 第 11 次
        result = _run(self.hook.pre_execute(_FakeWriteTool(), ctx, {"query": "x"}))
        assert isinstance(result, Reject)
        assert result.error_code == "rate_limit_exceeded"
        assert result.retry_after is not None
        assert 0 < result.retry_after <= 60

    # --- T4: 跨用户独立 ---
    def test_different_users_independent_counters(self):
        ctx_a = SimpleNamespace(user=SimpleNamespace(id=2004, is_authenticated=True))
        ctx_b = SimpleNamespace(user=SimpleNamespace(id=2005, is_authenticated=True))
        for _ in range(10):
            _run(self.hook.pre_execute(_FakeWriteTool(), ctx_a, {"query": "x"}))
        # user A 已满
        result_a = _run(self.hook.pre_execute(_FakeWriteTool(), ctx_a, {"query": "x"}))
        assert isinstance(result_a, Reject)
        # user B 不受影响
        result_b = _run(self.hook.pre_execute(_FakeWriteTool(), ctx_b, {"query": "x"}))
        assert result_b == {"query": "x"}

    def test_replay_bypasses_without_counting(self):
        ctx = SimpleNamespace(user=SimpleNamespace(id=2007, is_authenticated=True), replay=True)
        result = _run(self.hook.pre_execute(_FakeWriteTool(), ctx, {"query": "x"}))
        assert result == {"query": "x"}
        from django.core.cache import cache
        assert cache.get("smart_assistant:write_rate_limit:2007") is None

    # --- T5: 未认证放行(由 ChatMiddleware 兜底) ---
    def test_anonymous_passthrough(self):
        ctx = SimpleNamespace(user=SimpleNamespace(id=2006, is_authenticated=False))
        # 写工具 + 未认证 → 放行,不计数
        for _ in range(15):
            result = _run(self.hook.pre_execute(_FakeWriteTool(), ctx, {"query": "x"}))
            assert result == {"query": "x"}
        from django.core.cache import cache
        assert cache.get("smart_assistant:write_rate_limit:2006") is None


@pytest.mark.django_db
class TestExtractUserHelper:
    def test_toolcontext_attribute(self):
        from smart_assistant.tools.tool_context import ToolContext

        user_obj = SimpleNamespace(id=99)
        ctx = ToolContext(user=user_obj)
        assert _extract_user(ctx) is user_obj

    def test_dict_user_value(self):
        user_obj = SimpleNamespace(id=100)
        ctx = {"user": user_obj, "history": []}
        assert _extract_user(ctx) is user_obj

    def test_simple_namespace_fallback(self):
        user_obj = SimpleNamespace(id=101)
        ctx = SimpleNamespace(user=user_obj, history=[])
        assert _extract_user(ctx) is user_obj

    def test_no_user_returns_none(self):
        ctx = {"history": []}
        assert _extract_user(ctx) is None
        assert _extract_user(None) is None
