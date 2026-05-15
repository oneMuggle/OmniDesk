"""
Shared pytest fixtures for backend tests.
Provides authenticated API clients, user factories, and group fixtures.
"""
import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from users.models import CustomUser


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Clear Django cache between tests to prevent cross-test pollution.

    The LocMemCache in test settings persists across tests within the same
    process, which can cause stale group/permission data to leak between tests.
    """
    yield
    from django.core.cache import cache
    cache.clear()


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


@pytest.fixture
def mock_llm_response():
    """Mock LLM API response for smart assistant tests."""
    return {
        'choices': [
            {
                'message': {
                    'content': 'This is a mock LLM response.',
                    'role': 'assistant',
                },
                'finish_reason': 'stop',
            }
        ],
        'model': 'test-model',
    }


@pytest.fixture
def sample_document_data():
    """Sample document data for documents module tests."""
    return {
        'title': 'Test Document',
        'content': 'This is the content of a test document.',
        'template_name': 'default',
        'metadata': {
            'author': 'Test Author',
            'version': '1.0',
        },
    }


@pytest.fixture
def celery_task_mock(mocker):
    """Mock Celery task execution for async operation tests."""
    mock_task = mocker.MagicMock()
    mock_task.delay.return_value.id = 'test-task-id'
    mock_task.apply_async.return_value.id = 'test-task-id'
    return mock_task
