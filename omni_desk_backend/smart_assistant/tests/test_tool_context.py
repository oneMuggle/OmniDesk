"""ToolContext 数据类测试。"""
import pytest
from smart_assistant.tools.tool_context import ToolContext


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
    from rest_framework.test import APIRequestFactory
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = "mock_user"
    ctx = ToolContext.from_request(request)
    assert ctx.user == "mock_user"


def test_from_request_generates_request_id():
    from rest_framework.test import APIRequestFactory
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = "u"
    ctx = ToolContext.from_request(request)
    assert isinstance(ctx.request_id, str) and len(ctx.request_id) > 0
