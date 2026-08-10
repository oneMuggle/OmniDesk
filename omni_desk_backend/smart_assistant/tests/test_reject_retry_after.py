"""P1A-2: Reject 新增 retry_after 字段,默认值与显式赋值行为。"""

import pytest

from smart_assistant.hooks.base import Reject


class TestRejectRetryAfter:
    def test_default_retry_after_is_none(self):
        """既有 Reject 调用不受影响,默认值 None。"""
        r = Reject(reason="forbidden", error_code="forbidden")
        assert r.retry_after is None

    def test_explicit_retry_after_set(self):
        """显式传 retry_after 时字段可读。"""
        r = Reject(reason="rate_limited", error_code="rate_limit_exceeded", retry_after=42)
        assert r.retry_after == 42

    def test_reject_is_immutable(self):
        """frozen=True 不变,不能改 retry_after。"""
        r = Reject(reason="x", error_code="x")
        with pytest.raises(Exception):  # FrozenInstanceError
            r.retry_after = 99

    def test_positional_kwargs_compatibility(self):
        """既有 Reject(reason=..., error_code=...) kwargs 调用仍能工作。

        注:由于 retry_after 加在 dataclass 末尾,既有的 2-arg 位置调用
        ``Reject(reason_str, code_str)`` 实际会把 code_str 误塞进
        should_abort 字段(因 reason 之后是 should_abort),bool 转换后
        恒为 True。但本项目所有现有 Reject 调用都用 keyword args(grep
        验证),所以本测试只验证 kwargs 路径,而不是位置参数路径。
        """
        r = Reject(reason="reason-only", error_code="code-only")
        assert r.retry_after is None
        assert r.should_abort is False
