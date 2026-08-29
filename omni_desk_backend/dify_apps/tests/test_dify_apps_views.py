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
        assert response.data['count'] == 1

    def test_regular_user_cannot_create_dify_app(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.post('/api/dify-apps/', {
            'name': 'New Dify App',
            'embed_url': 'https://example.com/embed/new',
            'description': 'A new Dify app',
        }, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_create_dify_app(self, admin_client):
        response = admin_client.post('/api/dify-apps/', {
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

    def test_regular_user_cannot_update_dify_app(self, api_client, regular_user_obj):
        from dify_apps.models import DifyApp

        api_client.force_authenticate(user=regular_user_obj)
        app = DifyApp.objects.create(
            name='Protected App',
            embed_url='https://example.com/embed/protected',
        )
        response = api_client.put(f'/api/dify-apps/{app.pk}/', {
            'name': 'Changed App',
            'embed_url': 'https://example.com/embed/changed',
        }, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_cannot_partial_update_dify_app(self, api_client, regular_user_obj):
        from dify_apps.models import DifyApp

        api_client.force_authenticate(user=regular_user_obj)
        app = DifyApp.objects.create(
            name='Protected Patch App',
            embed_url='https://example.com/embed/protected-patch',
        )
        response = api_client.patch(f'/api/dify-apps/{app.pk}/', {
            'name': 'Changed Patch App',
        }, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

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

    def test_regular_user_cannot_delete_dify_app(self, api_client, regular_user_obj):
        from dify_apps.models import DifyApp

        api_client.force_authenticate(user=regular_user_obj)
        app = DifyApp.objects.create(
            name='Protected Delete App',
            embed_url='https://example.com/embed/protected-delete',
        )
        response = api_client.delete(f'/api/dify-apps/{app.pk}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert DifyApp.objects.filter(pk=app.pk).exists()

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
