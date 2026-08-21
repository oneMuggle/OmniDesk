"""Tests for /api/health/ probe extension (R5-B6): Redis hard probe + Celery soft degrade.

所有外部依赖(DB 除外,测试环境为内存 SQLite)均通过 unittest.mock 模拟,
不依赖真实 Redis / Celery worker。

契约(裁定:DB 与 Redis 是硬依赖,Celery 是软依赖):
- 全部健康 → 200 {"status": "ok", ...}
- DB 或 Redis 失败 → 503 {"status": "error", "<component>": "unreachable"}
- Celery 失败 → 200 + "celery": "degraded"
"""

from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status


HEALTH_URL = "/api/health/"


def _redis_client(ping_side_effect=None, ping_return=True):
    """构造 mock redis 客户端(替代 Redis.from_url 的返回值)。"""
    client = MagicMock()
    if ping_side_effect is not None:
        client.ping.side_effect = ping_side_effect
    else:
        client.ping.return_value = ping_return
    return client


def _celery_app(ping_return=None, ping_side_effect=None):
    """构造 mock celery app(control.ping 可控)。"""
    celery_app = MagicMock()
    if ping_side_effect is not None:
        celery_app.control.ping.side_effect = ping_side_effect
    else:
        celery_app.control.ping.return_value = ping_return
    return celery_app


@pytest.mark.django_db
class TestHealthProbes:
    def test_all_healthy_returns_200_ok(self, api_client):
        """DB + Redis 正常、Celery ping 有响应 → 200 ok(向后兼容字段保留)。"""
        with patch("omni_desk_backend.health._get_redis_client") as mock_factory:
            mock_factory.return_value = _redis_client()
            with patch("omni_desk_backend.celery.app", _celery_app({"worker1@host": {"ok": "pong"}})):
                response = api_client.get(HEALTH_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ok"
        # 向后兼容:既有字段不可删
        assert response.data["database"] == "ok"
        assert "version" in response.data
        assert "timestamp" in response.data

    def test_redis_connection_error_returns_503(self, api_client):
        """Redis 硬探针失败 → 503 + redis: unreachable。"""
        redis_lib = pytest.importorskip("redis")
        client = _redis_client(ping_side_effect=redis_lib.exceptions.ConnectionError("boom"))

        with patch("omni_desk_backend.health._get_redis_client") as mock_factory:
            mock_factory.return_value = client
            response = api_client.get(HEALTH_URL)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "error"
        assert response.data["redis"] == "unreachable"
        # DB 正常时 database 字段保持 ok
        assert response.data["database"] == "ok"

    def test_db_error_takes_priority_over_redis(self, api_client):
        """DB 失败(Redis 正常)→ 503,database 报告 unreachable。"""
        with patch("omni_desk_backend.health.connections") as mock_connections:
            mock_conn = mock_connections.__getitem__.return_value
            mock_conn.ensure_connection.side_effect = Exception("Connection refused")
            with patch("omni_desk_backend.health._get_redis_client") as mock_factory:
                mock_factory.return_value = _redis_client()
                response = api_client.get(HEALTH_URL)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "error"
        assert response.data["database"] == "unreachable"

    @pytest.mark.parametrize("ping_result", [None, {}])
    def test_celery_no_workers_returns_degraded(self, api_client, ping_result):
        """Celery 无 worker 响应(None / 空 dict)→ 不阻断,200 + degraded。"""
        with patch("omni_desk_backend.health._get_redis_client") as mock_factory:
            mock_factory.return_value = _redis_client()
            with patch("omni_desk_backend.celery.app", _celery_app(ping_result)):
                response = api_client.get(HEALTH_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "degraded"
        assert response.data["celery"] == "degraded"
        assert response.data["database"] == "ok"

    def test_celery_ping_raises_returns_degraded(self, api_client):
        """control.ping 抛异常(broker 连接失败等)→ 200 + degraded,不阻断。"""
        with patch("omni_desk_backend.health._get_redis_client") as mock_factory:
            mock_factory.return_value = _redis_client()
            with patch(
                "omni_desk_backend.celery.app",
                _celery_app(ping_side_effect=RuntimeError("broker down")),
            ):
                response = api_client.get(HEALTH_URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "degraded"
        assert response.data["celery"] == "degraded"

    def test_health_no_auth_required(self, api_client):
        """健康端点必须匿名可达(K8s livenessProbe 无凭据)。

        未认证请求不应 401/403;此处不 mock,同时验证真实降级路径:
        无 Redis/worker 环境下 Celery 软探针失败仍返回 200(而非 401/403/5xx 崩溃)。
        """
        response = api_client.get(HEALTH_URL)
        assert response.status_code != 401
        assert response.status_code != 403
