"""
Tests for permissions app: GroupViewSet, PageRouteViewSet,
GroupPermissionView, UserPermissionView, GroupedPermissionsView.
"""
import pytest
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser

from ..models import GroupPagePermission, PageRoute

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    user = CustomUser.objects.create_user(
        username='perm_admin', password='admin123', is_staff=True, is_superuser=True,
    )
    user.groups.add(admin_group)
    return user


@pytest.fixture
def regular_user(db):
    user_group, _ = Group.objects.get_or_create(name='User')
    user = CustomUser.objects.create_user(username='perm_user', password='user123')
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


@pytest.fixture
def page_route(db):
    return PageRoute.objects.create(
        name='测试页面', path='/test-page', component='TestPage',
    )


@pytest.fixture
def child_page(db, page_route):
    return PageRoute.objects.create(
        name='子页面', path='/test-page/child', component='TestPageChild', parent=page_route,
    )


# --- GroupViewSet Tests ---

class TestGroupViewSet:
    def test_admin_can_list_groups(self, admin_client, db):
        Group.objects.create(name='TestGroup')
        response = admin_client.get('/api/permissions/groups/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_regular_user_can_list_groups(self, regular_client):
        response = regular_client.get('/api/permissions/groups/')
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_create_group(self, admin_client):
        response = admin_client.post('/api/permissions/groups/', {'name': 'NewGroup'})
        assert response.status_code == status.HTTP_201_CREATED
        assert Group.objects.filter(name='NewGroup').exists()

    def test_regular_user_cannot_create_group(self, regular_client):
        response = regular_client.post('/api/permissions/groups/', {'name': 'NewGroup'})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_delete_group(self, admin_client):
        group = Group.objects.create(name='ToDelete')
        response = admin_client.delete(f'/api/permissions/groups/{group.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Group.objects.filter(id=group.id).exists()

    def test_regular_user_cannot_delete_group(self, regular_client):
        group = Group.objects.create(name='Protected')
        response = regular_client.delete(f'/api/permissions/groups/{group.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_user_cannot_access(self, api_client):
        response = api_client.get('/api/permissions/groups/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# --- PageRouteViewSet Tests ---

class TestPageRouteViewSet:
    def test_admin_can_list_pages(self, admin_client, page_route):
        response = admin_client.get('/api/permissions/pages/')
        assert response.status_code == status.HTTP_200_OK

    def test_pages_are_read_only(self, admin_client):
        response = admin_client.post('/api/permissions/pages/', {
            'name': '新建页面', 'path': '/new-page', 'component': 'NewPage',
        })
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_regular_user_cannot_create_page(self, regular_client):
        response = regular_client.post('/api/permissions/pages/', {
            'name': '新建页面', 'path': '/new-page', 'component': 'NewPage',
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_page_list_only_returns_top_level(self, admin_client, page_route, child_page):
        response = admin_client.get('/api/permissions/pages/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['id'] == page_route.id

    def test_page_includes_children(self, admin_client, page_route, child_page):
        response = admin_client.get('/api/permissions/pages/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data[0]['children']) == 1


# --- GroupPermissionView Tests ---

class TestGroupPermissionView:
    def test_admin_can_get_group_permissions(self, admin_client):
        group = Group.objects.create(name='PermGroup')
        response = admin_client.get(f'/api/permissions/groups/{group.id}/permissions/')
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_get_nonexistent_group_returns_404(self, admin_client):
        response = admin_client.get('/api/permissions/groups/99999/permissions/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_can_set_group_permissions(self, admin_client):
        group = Group.objects.create(name='SetPermGroup')
        content_type = ContentType.objects.create(app_label='test', model='testmodel')
        perm = Permission.objects.create(
            codename='test_perm', name='Test Perm', content_type=content_type,
        )
        response = admin_client.put(
            f'/api/permissions/groups/{group.id}/permissions/',
            {'permissions': [perm.id]},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert group.permissions.filter(id=perm.id).exists()

    def test_regular_user_cannot_set_group_permissions(self, regular_client):
        group = Group.objects.create(name='ReadOnlyGroup')
        response = regular_client.put(
            f'/api/permissions/groups/{group.id}/permissions/',
            {'permissions': []},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# --- UserPermissionView Tests ---

class TestUserPermissionView:
    def test_user_can_get_own_permissions(self, regular_client):
        response = regular_client.get('/api/permissions/users/me/permissions/')
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_superuser_gets_all_pages(self, admin_client, page_route):
        response = admin_client.get('/api/permissions/users/me/permissions/')
        assert response.status_code == status.HTTP_200_OK

    def test_regular_user_gets_pages_from_group(self, regular_client, page_route):
        user_group = Group.objects.get(name='User')
        GroupPagePermission.objects.create(group=user_group, page=page_route)
        response = regular_client.get('/api/permissions/users/me/permissions/')
        assert response.status_code == status.HTTP_200_OK
        assert any(p['id'] == page_route.id for p in response.data)

    def test_unauthenticated_cannot_access(self, api_client):
        response = api_client.get('/api/permissions/users/me/permissions/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# --- GroupedPermissionsView Tests ---

class TestGroupedPermissionsView:
    def test_admin_can_list_grouped_permissions(self, admin_client):
        response = admin_client.get('/api/permissions/permissions/grouped/')
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

    def test_regular_user_can_list_grouped_permissions(self, regular_client):
        response = regular_client.get('/api/permissions/permissions/grouped/')
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_cannot_access(self, api_client):
        response = api_client.get('/api/permissions/permissions/grouped/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
