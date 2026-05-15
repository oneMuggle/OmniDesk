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
