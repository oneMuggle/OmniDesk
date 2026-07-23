"""ToolContext 数据类测试。"""
import pytest
from smart_assistant.tools.tool_context import ToolContext
from smart_assistant.scope import SmartAssistantScope


def test_create_with_user_only():
    ctx = ToolContext(user="alice")
    assert ctx.user == "alice"
    assert ctx.request_id  # 自动生成
    assert ctx.history == []


def test_request_id_unique():
    a, b = ToolContext(user="x"), ToolContext(user="x")
    assert a.request_id != b.request_id


def test_frozen_cannot_mutate():
    ctx = ToolContext(user="alice")
    with pytest.raises(Exception):  # FrozenInstanceError
        ctx.user = "bob"


def test_from_request_with_drf_request():
    from unittest.mock import Mock
    from rest_framework.test import APIRequestFactory
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = Mock(is_superuser=False, has_perm=lambda perm: False)
    ctx = ToolContext.from_request(request)
    assert ctx.user is request.user


def test_from_request_generates_request_id():
    from unittest.mock import Mock
    from rest_framework.test import APIRequestFactory
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = Mock(is_superuser=False, has_perm=lambda perm: False)
    ctx = ToolContext.from_request(request)
    assert isinstance(ctx.request_id, str) and len(ctx.request_id) > 0


def test_from_request_preserves_existing_request_id():
    """from_request 应保留 request 上已有的 request_id(用于日志关联)。"""
    from unittest.mock import Mock
    from rest_framework.test import APIRequestFactory
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = Mock(is_superuser=False, has_perm=lambda perm: False)
    request.request_id = "preset-id-12345"
    ctx = ToolContext.from_request(request)
    assert ctx.request_id == "preset-id-12345"


def test_tool_context_default_scope_is_self():
    """ToolContext 默认 scope = SELF"""
    ctx = ToolContext(user="u")
    assert ctx.scope == SmartAssistantScope.SELF


def test_tool_context_explicit_scope():
    """ToolContext 接受显式 scope 参数"""
    ctx = ToolContext(user="u", scope=SmartAssistantScope.DEPARTMENT)
    assert ctx.scope == SmartAssistantScope.DEPARTMENT


def test_from_request_calls_resolve_scope(monkeypatch):
    """from_request 调用 resolve_scope(user) 自动派生 scope"""
    from smart_assistant.tools import tool_context as tc_mod

    called = []
    monkeypatch.setattr(tc_mod, "resolve_scope", lambda u: called.append(u) or SmartAssistantScope.GLOBAL)

    from rest_framework.test import APIRequestFactory
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = "alice"

    ctx = ToolContext.from_request(request)
    assert ctx.user == "alice"
    assert called == ["alice"]
    assert ctx.scope == SmartAssistantScope.GLOBAL
