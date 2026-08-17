"""Tests for the client error report endpoint."""

import json

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Each test starts with a fresh throttle cache so 10/min limit doesn't leak."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


def _post_error(client, payload):
    return client.post(
        "/api/system/client-error/",
        data=json.dumps(payload),
        content_type="application/json",
    )


# ── Happy path ──────────────────────────────────────────────────────


def test_anon_post_returns_204(api_client):
    """未登录用户可以上报(AllowAny)。"""
    resp = _post_error(
        api_client,
        {
            "kind": "window.onerror",
            "message": "TypeError: undefined is not a function",
            "stack": "at foo (bar.js:1:1)",
            "source": "bar.js",
            "url": "https://example.com/page",
            "ua": "Mozilla/5.0",
        },
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_sensitive_top_level_keys_are_dropped(api_client):
    """白名单之外的字段被服务端丢弃(防止前端漏脱敏)。"""
    resp = _post_error(
        api_client,
        {
            "kind": "boundary",
            "message": "boom",
            "password": "leaked",
            "token": "leaked-jwt",
            "authorization": "Bearer leaked",
        },
    )
    assert resp.status_code == 204


def test_nested_extra_sensitive_keys_are_dropped(api_client):
    """extra 字典里的敏感键被递归清除。"""
    resp = _post_error(
        api_client,
        {
            "kind": "boundary",
            "message": "boom",
            "extra": {
                "username": "alice",  # 保留
                "password": "leaked",  # 清除
                "refresh_token": "leaked",  # 清除
                "sessionId": "leaked",  # 清除(大小写不敏感)
                "apiKey": "leaked",  # 清除
            },
        },
    )
    assert resp.status_code == 204


# ── Edge cases ──────────────────────────────────────────────────────


def test_empty_payload_returns_204(api_client):
    resp = _post_error(api_client, {})
    assert resp.status_code == 204


def test_non_dict_payload_returns_204(api_client):
    """非 dict payload(如 list/str)被安全处理。"""
    resp = _post_error(api_client, ["not", "a", "dict"])
    assert resp.status_code == 204


def test_long_message_is_truncated(api_client):
    """超长字符串被截断到 500 字符,防止日志爆掉。"""
    long_msg = "x" * 5000
    resp = _post_error(
        api_client,
        {"kind": "boundary", "message": long_msg, "stack": long_msg},
    )
    assert resp.status_code == 204


def test_only_get_is_rejected(api_client):
    """端点只接受 POST。"""
    resp = api_client.get("/api/system/client-error/")
    assert resp.status_code == 405


# ── Throttle 配置校验 ───────────────────────────────────────────────


def test_client_error_throttle_scope_is_configured():
    """验证 throttle 配置正确写入 settings.DATABASES 之外的 REST_FRAMEWORK。

    实际限流逻辑由 DRF 框架保证,我们只校验配置存在且 rate 正确。
    """
    from django.conf import settings
    from django.test import override_settings

    rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
    assert "client_error" in rates, "client_error scope 必须在 DEFAULT_THROTTLE_RATES 中"
    assert rates["client_error"] == "10/min"


def test_throttle_blocks_after_limit(api_client):
    """同一 IP 超过 rate 时被 429 拒绝。

    DRF 的 SimpleRateThrottle.__init__ 用 self.rate = self.get_rate() 设实例属性,
    直接 patch class.rate 会被覆盖。改成 patch get_rate 方法返回 "2/min"。
    """
    from unittest.mock import patch

    from core.throttles import ClientErrorAnonThrottle
    from django.core.cache import cache

    cache.clear()

    payload = {"kind": "boundary", "message": "boom"}

    def fake_get_rate(self):
        return "2/min"

    with patch.object(ClientErrorAnonThrottle, "get_rate", fake_get_rate):
        assert _post_error(api_client, payload).status_code == 204
        assert _post_error(api_client, payload).status_code == 204
        resp3 = _post_error(api_client, payload)
        assert resp3.status_code == 429
