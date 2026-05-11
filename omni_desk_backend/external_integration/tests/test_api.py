import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from ..models import ExternalLink, IntegrationService

CustomUser = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='testuser', password='testpass')


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def integration_service(db):
    return IntegrationService.objects.create(
        name='Test Dify',
        slug='test-dify',
        integration_type='api',
        endpoint_url='http://dify.internal/api/v1',
        api_key='test-key',
    )


@pytest.mark.django_db
class TestIntegrationServiceAPI:
    def test_list_services_unauthenticated(self, api_client):
        resp = api_client.get('/api/external/integrations/')
        assert resp.status_code == 401

    def test_list_services_empty(self, authenticated_client):
        resp = authenticated_client.get('/api/external/integrations/')
        assert resp.status_code == 200
        assert resp.data == []

    def test_list_services(self, authenticated_client, integration_service):
        resp = authenticated_client.get('/api/external/integrations/')
        assert resp.status_code == 200
        assert len(resp.data) == 1
        assert resp.data[0]['slug'] == 'test-dify'

    def test_get_service_by_slug(self, authenticated_client, integration_service):
        resp = authenticated_client.get(f'/api/external/integrations/{integration_service.slug}/')
        assert resp.status_code == 200
        assert resp.data['name'] == 'Test Dify'

    def test_embed_not_iframe_type(self, authenticated_client, integration_service):
        resp = authenticated_client.get(f'/api/external/integrations/{integration_service.slug}/embed/')
        assert resp.status_code == 400

    def test_proxy_not_api_type(self, authenticated_client):
        svc = IntegrationService.objects.create(
            name='Test Iframe',
            slug='test-iframe',
            integration_type='iframe',
            endpoint_url='http://example.com',
        )
        resp = authenticated_client.post(f'/api/external/integrations/{svc.slug}/proxy/', {})
        assert resp.status_code == 400
