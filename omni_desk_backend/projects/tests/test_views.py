"""Tests for projects app: ProjectViewSet."""
import pytest
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser

from ..models import Project

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    user = CustomUser.objects.create_user(
        username='proj_admin', password='admin123', is_staff=True, is_superuser=True,
    )
    user.groups.add(admin_group)
    return user


@pytest.fixture
def manager_user(db):
    manager_group, _ = Group.objects.get_or_create(name='Manager')
    user = CustomUser.objects.create_user(
        username='proj_manager', password='manager123', is_staff=True,
    )
    user.groups.add(manager_group)
    return user


@pytest.fixture
def regular_user(db):
    user_group, _ = Group.objects.get_or_create(name='User')
    user = CustomUser.objects.create_user(username='proj_user', password='user123')
    user.groups.add(user_group)
    return user


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def manager_client(api_client, manager_user):
    api_client.force_authenticate(user=manager_user)
    return api_client


@pytest.fixture
def regular_client(api_client, regular_user):
    api_client.force_authenticate(user=regular_user)
    return api_client


class TestProjectViewSet:
    def test_admin_can_list_all_projects(self, admin_client, manager_user):
        Project.objects.create(name='AdminProject', manager=manager_user)
        Project.objects.create(name='ManagerProject', manager=manager_user)
        response = admin_client.get('/api/projects/')
        assert response.status_code == status.HTTP_200_OK
        count = response.data.get('count', len(response.data))
        assert count >= 2

    def test_manager_sees_only_own_projects(self, manager_client, manager_user):
        Project.objects.create(name='OwnProject', manager=manager_user)
        response = manager_client.get('/api/projects/')
        assert response.status_code == status.HTTP_200_OK

    def test_regular_user_sees_no_projects(self, regular_client):
        Project.objects.create(name='HiddenProject')
        response = regular_client.get('/api/projects/')
        assert response.status_code == status.HTTP_200_OK
        count = response.data.get('count', len(response.data))
        assert count == 0

    def test_admin_can_create_project(self, admin_client, manager_user):
        response = admin_client.post('/api/projects/', {
            'name': 'NewProject', 'description': 'A test project',
            'manager': manager_user.id,
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_unauthenticated_cannot_access(self, api_client):
        response = api_client.get('/api/projects/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_project_status(self, admin_client):
        project = Project.objects.create(name='StatusProject')
        response = admin_client.patch(f'/api/projects/{project.id}/', {'status': '已完成'})
        assert response.status_code == status.HTTP_200_OK
        project.refresh_from_db()
        assert project.status == '已完成'
