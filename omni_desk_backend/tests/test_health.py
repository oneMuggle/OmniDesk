"""
Tests for health check endpoint.

R5-B6 起 /api/health/ 扩展为:DB 与 Redis 硬探针(失败 → 503)、Celery 软探针
(失败 → 200 + degraded)。本文件保留既有 DB 场景覆盖;Redis/Celery 组合场景
见 omni_desk_backend/tests/test_health_probes.py。

所有外部依赖(DB 除外,测试环境为内存 SQLite)均通过 unittest.mock 模拟,
不依赖真实 Redis / Celery worker。
"""
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status


HEALTH_URL = '/api/health/'


def _redis_client_ok():
    """正常响应 ping 的 mock redis 客户端。"""
    client = MagicMock()
    client.ping.return_value = True
    return client


def _celery_app_workers():
    """有 worker 响应的 mock celery app。"""
    celery_app = MagicMock()
    celery_app.control.ping.return_value = {"worker1@host": {"ok": "pong"}}
    return celery_app


@pytest.fixture
def healthy_probes():
    """同时 mock Redis 与 Celery 为健康状态,隔离真实服务。"""
    with (
        patch("omni_desk_backend.health._get_redis_client", return_value=_redis_client_ok()),
        patch("omni_desk_backend.celery.app", _celery_app_workers()),
    ):
        yield


@pytest.mark.django_db
class TestHealthCheck:
    def test_health_check_success(self, api_client, healthy_probes):
        response = api_client.get(HEALTH_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'ok'
        assert response.data['database'] == 'ok'
        assert 'version' in response.data
        assert 'timestamp' in response.data

    def test_health_check_no_auth_required(self, api_client, healthy_probes):
        """Health check should be accessible without authentication."""
        response = api_client.get(HEALTH_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'ok'

    def test_health_check_db_error(self, api_client, healthy_probes):
        """Health check should return 503 when database is unavailable."""
        with patch('omni_desk_backend.health.connections') as mock_connections:
            mock_conn = mock_connections.__getitem__.return_value
            mock_conn.ensure_connection.side_effect = Exception('Connection refused')

            response = api_client.get(HEALTH_URL)
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert response.data['status'] == 'error'
            assert response.data['database'] == 'unreachable'
            # 错误详情不得泄露给未认证调用方，仅返回固定文案
            assert 'Connection refused' not in str(response.data)

    def test_health_check_redis_error(self, api_client):
        """Health check should return 503 when Redis is unavailable (hard dependency)."""
        redis_lib = pytest.importorskip('redis')
        client = MagicMock()
        client.ping.side_effect = redis_lib.exceptions.ConnectionError('boom')

        with patch('omni_desk_backend.health._get_redis_client', return_value=client):
            response = api_client.get(HEALTH_URL)
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert response.data['status'] == 'error'
            assert response.data['redis'] == 'unreachable'
            assert 'boom' not in str(response.data)
