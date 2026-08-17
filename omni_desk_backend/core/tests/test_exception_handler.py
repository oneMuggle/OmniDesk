"""omnidesk_exception_handler 单元测试(P1-8)

覆盖 4 类场景:
- 4xx 路径:ValidationError → DRF 默认包装 + request_id 注入,无 debug 字段
- 5xx 路径:Exception → logger.error + 仅 DEBUG 下发 stack
- request_id 缺失:ContextVar 为 None 时不报错,也不注入空字段
- 非 DRF 已知异常(如 Django Http404):返回 None 让 Django 兜底
"""

import logging
from unittest.mock import patch

import pytest
from django.http import Http404
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from core.exception_handler import omnidesk_exception_handler
from observability.context import request_id_var


@pytest.fixture
def fake_context():
    """构造 DRF 风格的 context 字典,带一个最小 view。"""

    class _StubView(APIView):
        pass

    factory = APIRequestFactory()
    request = factory.get("/")
    return {"view": _StubView(), "request": request, "args": (), "kwargs": {}}


@pytest.fixture(autouse=True)
def _reset_request_id():
    """每个测试前后重置 ContextVar,避免污染。"""
    token = request_id_var.set(None)
    try:
        yield
    finally:
        request_id_var.reset(token)


def test_4xx_keeps_drf_envelope_and_adds_request_id(fake_context, caplog):
    """ValidationError → DRF 默认 detail 包装 + request_id 字段,无 logger 噪声。"""
    request_id_var.set("rid-test-123")
    with caplog.at_level(logging.ERROR, logger="core.exception_handler"):
        response = omnidesk_exception_handler(ValidationError("bad input"), fake_context)

    assert response is not None
    assert response.status_code == 400
    # DRF 把单条 ValidationError 包成 list[ErrorDetail],handler 把它装进 {detail: [...]}
    assert "bad input" in str(response.data["detail"])
    assert response.data["request_id"] == "rid-test-123"
    # 4xx 不应触发 logger.error 也不应下发 debug
    assert "debug" not in response.data
    assert not [r for r in caplog.records if r.levelno == logging.ERROR]


def test_5xx_logs_stack_and_injects_request_id(fake_context, caplog):
    """裸 Exception → 500 + logger.error(exc_info=True) + request_id 注入。"""
    request_id_var.set("rid-500-abc")
    with caplog.at_level(logging.ERROR, logger="core.exception_handler"):
        response = omnidesk_exception_handler(RuntimeError("boom"), fake_context)

    assert response is not None
    assert response.status_code == 500
    assert response.data["request_id"] == "rid-500-abc"
    # logger.error 被调用,exc_info=True 让 stack 进入 record
    err_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(err_records) == 1
    assert err_records[0].exc_info is not None  # type: ignore[attr-defined]
    assert "boom" in str(err_records[0].getMessage())


def test_5xx_debug_field_only_when_settings_debug(fake_context, settings):
    """DEBUG=False 下不应下发 stack;DEBUG=True 才下 debug 字段。"""
    request_id_var.set("rid-debug")
    settings.DEBUG = False
    response = omnidesk_exception_handler(RuntimeError("boom"), fake_context)
    assert response is not None
    assert "debug" not in response.data

    settings.DEBUG = True
    response = omnidesk_exception_handler(RuntimeError("boom2"), fake_context)
    assert response is not None
    assert "debug" in response.data
    assert response.data["debug"]["type"] == "RuntimeError"
    assert isinstance(response.data["debug"]["stack"], list)
    assert len(response.data["debug"]["stack"]) <= 20


def test_no_request_id_does_not_inject_empty(fake_context):
    """ContextVar 为 None 时不注入空 request_id 字段。"""
    response = omnidesk_exception_handler(ValidationError("x"), fake_context)
    assert response is not None
    assert "request_id" not in response.data


def test_django_http404_passes_through_with_request_id(fake_context):
    """Django Http404 被 DRF 默认 handler 翻译为 404 Response(并非 None)。

    实际场景:DRF 把 Django Http404 当 NotFound 走,最终产 status_code=404。
    本 handler 只追加 request_id,不改它的 status code 与 detail 文案。
    """
    request_id_var.set("rid-404")
    response = omnidesk_exception_handler(Http404("nope"), fake_context)
    assert response is not None
    assert response.status_code == 404
    assert response.data["request_id"] == "rid-404"


def test_view_name_includes_module_path(fake_context, caplog):
    """5xx 日志必须包含 view 的 module.path.ClassName,便于事故定位。"""
    request_id_var.set("rid-viewname")
    with caplog.at_level(logging.ERROR, logger="core.exception_handler"):
        omnidesk_exception_handler(RuntimeError("boom"), fake_context)
    err = [r for r in caplog.records if r.levelno == logging.ERROR][0]
    msg = err.getMessage()
    assert "_StubView" in msg


def test_logger_error_called_with_exc_info(fake_context):
    """直接 patch logger.error,确认 exc_info=True 标志传入。"""
    with patch("core.exception_handler.logger.error") as mock_err:
        omnidesk_exception_handler(RuntimeError("boom"), fake_context)
    assert mock_err.called
    _, kwargs = mock_err.call_args
    assert kwargs.get("exc_info") is True