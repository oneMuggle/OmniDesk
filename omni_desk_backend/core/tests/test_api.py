import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
class TestCoreAPI:
    def test_version_endpoint(self, regular_client):
        response = regular_client.get(reverse('version-info'))
        assert response.status_code == status.HTTP_200_OK
        assert 'version' in response.data
        assert 'build_time' in response.data
        assert 'django_version' in response.data

    def test_changelog_endpoint(self, regular_client):
        response = regular_client.get(reverse('changelog'))
        assert response.status_code == status.HTTP_200_OK
        assert 'changelog' in response.data
        assert isinstance(response.data['changelog'], str)

    def test_migration_status_endpoint(self, regular_client):
        response = regular_client.get(reverse('migration-status'))
        assert response.status_code == status.HTTP_200_OK
        assert 'applied' in response.data
        assert 'pending' in response.data
        assert 'applied_count' in response.data
        assert 'pending_count' in response.data
        assert 'has_destructive' in response.data

    def test_version_unauthenticated(self, api_client):
        response = api_client.get(reverse('version-info'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_changelog_unauthenticated(self, api_client):
        response = api_client.get(reverse('changelog'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_migration_unauthenticated(self, api_client):
        response = api_client.get(reverse('migration-status'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestReadinessCheck:
    """Tests for /api/system/ready/ readiness endpoint (no auth required)."""

    def test_readiness_returns_200_when_db_ok(self, api_client):
        response = api_client.get(reverse('readiness-check'))
        # 200 if all critical checks pass; 503 if any critical check fails
        assert response.status_code in (200, 503)
        assert 'status' in response.data
        assert 'checks' in response.data
        assert response.data['status'] in ('ready', 'not_ready')
        # database should always be ok in test env (in-memory SQLite)
        assert 'database' in response.data['checks']
        assert response.data['checks']['database']['status'] == 'ok'

    def test_readiness_does_not_require_auth(self, api_client):
        """AllowAny: 即使未登录也允许访问(用于 K8s readinessProbe)"""
        response = api_client.get(reverse('readiness-check'))
        assert response.status_code in (200, 503)
        assert response.status_code != 401
        assert response.status_code != 403

    def test_readiness_includes_cache_check(self, api_client):
        response = api_client.get(reverse('readiness-check'))
        assert 'cache' in response.data['checks']
        # LocMemCache in test should be ok
        assert response.data['checks']['cache']['status'] == 'ok'

    def test_readiness_includes_celery_status(self, api_client):
        response = api_client.get(reverse('readiness-check'))
        assert 'celery' in response.data['checks']
        # celery status may be 'ok' / 'warning' / 'skipped' / 'error' depending on env
        assert response.data['checks']['celery']['status'] in ('ok', 'warning', 'skipped', 'error')
