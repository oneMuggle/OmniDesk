"""Tests for config app: PageVisibilityViewSet, OllamaConfigViewSet."""
import pytest
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser

from ..models import OllamaConfig, Page, PageVisibility

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    user = CustomUser.objects.create_user(
        username='cfg_admin', password='admin123', is_staff=True, is_superuser=True,
    )
    user.groups.add(admin_group)
    return user


@pytest.fixture
def regular_user(db):
    user_group, _ = Group.objects.get_or_create(name='User')
    user = CustomUser.objects.create_user(username='cfg_user', password='user123')
    user.groups.add(user_group)
    return user


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def regular_client(api_client, regular_user):
    api_client.force_authenticate(user=regular_user)
    return api_client


# --- PageVisibilityViewSet Tests ---

class TestPageVisibilityViewSet:
    def test_admin_can_list_page_visibility(self, admin_client):
        Page.objects.create(name='Test', path='/test')
        Group.objects.create(name='TestGroup')
        response = admin_client.get('/api/config/page-visibility/')
        assert response.status_code == status.HTTP_200_OK
        assert 'pages' in response.data
        assert 'groups' in response.data
        assert 'visibility' in response.data

    def test_admin_can_set_visibility(self, admin_client):
        page = Page.objects.create(name='P1', path='/p1')
        group = Group.objects.create(name='G1')
        response = admin_client.post('/api/config/page-visibility/', {
            'page_id': page.id, 'group_id': group.id, 'is_visible': True,
        })
        assert response.status_code == status.HTTP_200_OK
        assert PageVisibility.objects.count() == 1

    def test_admin_missing_fields_returns_400(self, admin_client):
        response = admin_client.post('/api/config/page-visibility/', {'page_id': 1})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_regular_user_cannot_modify_visibility(self, regular_client):
        page = Page.objects.create(name='P2', path='/p2')
        group = Group.objects.create(name='G2')
        response = regular_client.post('/api/config/page-visibility/', {
            'page_id': page.id, 'group_id': group.id, 'is_visible': True,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_access(self, api_client):
        response = api_client.get('/api/config/page-visibility/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# --- OllamaConfigViewSet Tests ---

class TestOllamaConfigViewSet:
    def test_admin_can_list_ollama_configs(self, admin_client):
        OllamaConfig.objects.create(alias='test', api_endpoint='http://localhost:11434', model='test-model')
        response = admin_client.get('/api/config/ollama-configs/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_admin_can_create_ollama_config(self, admin_client):
        response = admin_client.post('/api/config/ollama-configs/', {
            'alias': 'new-config', 'api_endpoint': 'http://localhost:11434', 'model': 'deepseek-r1',
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_admin_can_update_ollama_config(self, admin_client):
        cfg = OllamaConfig.objects.create(alias='upd', api_endpoint='http://old', model='old-model')
        response = admin_client.patch(f'/api/config/ollama-configs/{cfg.id}/', {'model': 'new-model'})
        assert response.status_code == status.HTTP_200_OK
        cfg.refresh_from_db()
        assert cfg.model == 'new-model'

    def test_admin_can_delete_ollama_config(self, admin_client):
        cfg = OllamaConfig.objects.create(alias='del', api_endpoint='http://del', model='del-model')
        response = admin_client.delete(f'/api/config/ollama-configs/{cfg.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not OllamaConfig.objects.filter(id=cfg.id).exists()

    def test_regular_user_cannot_create_config(self, regular_client):
        response = regular_client.post('/api/config/ollama-configs/', {
            'alias': 'unauthorized', 'api_endpoint': 'http://localhost:11434', 'model': 'm',
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_setting_default_unsets_others(self, admin_client):
        c1 = OllamaConfig.objects.create(alias='c1', api_endpoint='http://localhost:11434', model='m', is_default=True)
        c2 = OllamaConfig.objects.create(alias='c2', api_endpoint='http://localhost:11434', model='m')
        response = admin_client.patch(f'/api/config/ollama-configs/{c2.id}/', {'is_default': True})
        assert response.status_code == status.HTTP_200_OK
        c1.refresh_from_db()
        c2.refresh_from_db()
        assert c1.is_default is False
        assert c2.is_default is True
