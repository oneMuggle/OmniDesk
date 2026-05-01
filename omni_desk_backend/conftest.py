"""
Shared pytest fixtures for backend tests.
Provides authenticated API clients, user factories, and group fixtures.
"""
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from users.models import CustomUser


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user_obj(db):
    """Create an admin user with Admin group."""
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    user = CustomUser.objects.create_user(
        username='admin_test',
        password='admin123',
        is_staff=True,
        is_superuser=True,
    )
    user.groups.add(admin_group)
    return user


@pytest.fixture
def manager_user_obj(db):
    """Create a manager user with Manager group."""
    manager_group, _ = Group.objects.get_or_create(name='Manager')
    user = CustomUser.objects.create_user(
        username='manager_test',
        password='manager123',
        is_staff=True,
    )
    user.groups.add(manager_group)
    return user


@pytest.fixture
def regular_user_obj(db):
    """Create a regular user with User group."""
    user_group, _ = Group.objects.get_or_create(name='User')
    user = CustomUser.objects.create_user(
        username='regular_test',
        password='user123',
    )
    user.groups.add(user_group)
    return user


@pytest.fixture
def authenticated_client(api_client, admin_user_obj):
    """Return an APIClient authenticated as admin."""
    api_client.force_authenticate(user=admin_user_obj)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user_obj):
    """Alias for authenticated_client."""
    api_client.force_authenticate(user=admin_user_obj)
    return api_client


@pytest.fixture
def manager_client(api_client, manager_user_obj):
    """Return an APIClient authenticated as manager."""
    api_client.force_authenticate(user=manager_user_obj)
    return api_client


@pytest.fixture
def regular_client(api_client, regular_user_obj):
    """Return an APIClient authenticated as regular user."""
    api_client.force_authenticate(user=regular_user_obj)
    return api_client
