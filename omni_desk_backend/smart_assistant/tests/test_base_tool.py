"""Tests for BaseTool scope filter abstract methods (Task 3).

These tests verify the new abstract method layer added to BaseTool for
cross-module aggregation with layered permissions. They cover:

1. supports_scope_filter property behavior
2. get_queryset_for_scope dispatch logic (SELF/DEPARTMENT/GLOBAL)
3. _scope_self abstract enforcement
4. Backward compatibility with legacy tools that don't implement new methods
"""

import pytest
from unittest.mock import Mock

from smart_assistant.scope import SmartAssistantScope
from smart_assistant.tools.base import BaseTool
from smart_assistant.tools.tool_context import ToolContext


class _StubTool(BaseTool):
    """用于测试基类的 stub 工具"""

    name = "stub"
    description = "stub"
    intent_type = "stub"

    def execute(self, query, context):
        return {"found": True}

    def build_base_queryset(self):
        return Mock(name="base_qs")

    def _scope_self(self, qs, ctx):
        # 注意:Mock(name=...) 的 name 参数只影响 repr,不会让 .name 属性
        # 返回该字符串。必须显式赋值,才能让测试断言 result.name == "self_qs" 成立。
        m = Mock()
        m.name = "self_qs"
        return m


def test_supports_scope_filter_true_when_methods_implemented():
    """实现了 build_base_queryset + _scope_self → supports_scope_filter = True"""
    t = _StubTool()
    assert t.supports_scope_filter is True


def test_supports_scope_filter_false_for_legacy_tool():
    """未实现新方法(走旧路径)→ supports_scope_filter = False"""
    class Legacy(BaseTool):
        name = "l"
        description = "l"
        intent_type = "l"
        def execute(self, q, c): return {}
    assert Legacy().supports_scope_filter is False


def test_get_queryset_for_scope_self_dispatches_to_scope_self():
    """scope=SELF → 调 _scope_self(base_qs, ctx)"""
    t = _StubTool()
    ctx = ToolContext(user="u", scope=SmartAssistantScope.SELF)
    result = t.get_queryset_for_scope("base", ctx)
    assert result == "self_qs" or result.name == "self_qs"


def test_get_queryset_for_scope_global_returns_base_qs():
    """scope=GLOBAL → 直接返回 base_qs,不过滤"""
    t = _StubTool()
    ctx = ToolContext(user="u", scope=SmartAssistantScope.GLOBAL)
    base = Mock(name="base")
    assert t.get_queryset_for_scope(base, ctx) is base


def test_get_queryset_for_scope_department_uses_default():
    """默认 _scope_department = 返回 base_qs(子类可重写)"""
    t = _StubTool()
    ctx = ToolContext(user="u", scope=SmartAssistantScope.DEPARTMENT)
    base = Mock(name="base")
    assert t.get_queryset_for_scope(base, ctx) is base


def test_scope_self_not_implemented_raises():
    """未实现 _scope_self 时调 _scope_self → NotImplementedError"""
    class Incomplete(BaseTool):
        name = "i"; description = "i"; intent_type = "i"
        def execute(self, q, c): return {}
    with pytest.raises(NotImplementedError):
        Incomplete()._scope_self("qs", Mock(scope=SmartAssistantScope.SELF))


def test_legacy_execute_signature_still_works():
    """旧的 execute(query, context) 调用方式仍工作(向后兼容)"""
    t = _StubTool()
    result = t.execute("hello", Mock())
    assert result == {"found": True}