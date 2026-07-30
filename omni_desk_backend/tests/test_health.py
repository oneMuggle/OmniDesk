"""
Tests for health check endpoint.
"""
from unittest.mock import patch

import pytest
from rest_framework import status


@pytest.mark.django_db
class TestHealthCheck:
    def test_health_check_success(self, api_client):
        response = api_client.get('/api/health/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'ok'
        assert response.data['database'] == 'ok'
        assert 'version' in response.data
        assert 'timestamp' in response.data

    def test_health_check_no_auth_required(self, api_client):
        """Health check should be accessible without authentication."""
        response = api_client.get('/api/health/')
        assert response.status_code == status.HTTP_200_OK

    def test_health_check_db_error(self, api_client):
        """Health check should return 503 when database is unavailable."""
        with patch('omni_desk_backend.health.connections') as mock_connections:
            mock_conn = mock_connections.__getitem__.return_value
            mock_conn.ensure_connection.side_effect = Exception('Connection refused')

            response = api_client.get('/api/health/')
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert response.data['status'] == 'error'
            assert response.data['database'] == 'error'
            # 错误详情不得泄露给未认证调用方，仅返回固定文案
            assert response.data['database_error'] == 'database error'
            assert 'Connection refused' not in str(response.data)
