"""
Tests for dify_apps module (DifyApp CRUD).
"""
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestDifyAppViewSet:
    def test_list_dify_apps_unauthenticated(self, api_client):
        response = api_client.get('/api/dify-apps/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_dify_apps_authenticated(self, api_client, regular_user_obj):
        from dify_apps.models import DifyApp
        api_client.force_authenticate(user=regular_user_obj)
        DifyApp.objects.create(
            name='Test App',
            embed_url='https://example.com/embed/test',
            description='Test app',
        )
        response = api_client.get('/api/dify-apps/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_create_dify_app(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.post('/api/dify-apps/', {
            'name': 'New Dify App',
            'embed_url': 'https://example.com/embed/new',
            'description': 'A new Dify app',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New Dify App'

    def test_retrieve_dify_app(self, admin_client):
        from dify_apps.models import DifyApp
        app = DifyApp.objects.create(
            name='Retrieve Test',
            embed_url='https://example.com/embed/retrieve',
        )
        response = admin_client.get(f'/api/dify-apps/{app.pk}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Retrieve Test'

    def test_update_dify_app(self, admin_client):
        from dify_apps.models import DifyApp
        app = DifyApp.objects.create(
            name='Old Name',
            embed_url='https://example.com/embed/old',
        )
        response = admin_client.patch(f'/api/dify-apps/{app.pk}/', {
            'name': 'Updated Name',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Name'

    def test_delete_dify_app(self, admin_client):
        from dify_apps.models import DifyApp
        app = DifyApp.objects.create(
            name='To Delete',
            embed_url='https://example.com/embed/delete',
        )
        response = admin_client.delete(f'/api/dify-apps/{app.pk}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DifyApp.objects.filter(pk=app.pk).exists()

    def test_create_dify_app_duplicate_name(self, admin_client):
        from dify_apps.models import DifyApp
        DifyApp.objects.create(
            name='Unique App',
            embed_url='https://example.com/embed/unique',
        )
        response = admin_client.post('/api/dify-apps/', {
            'name': 'Unique App',
            'embed_url': 'https://example.com/embed/another',
        }, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
