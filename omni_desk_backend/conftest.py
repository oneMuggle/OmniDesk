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


# =============================================================================
# Model Factory Helpers
# =============================================================================
# Usage: call the factory function directly in tests.
# Example: project = create_project(db, name='My Project')
# These are plain functions, not pytest fixtures, so they can be called
# with custom arguments from within test functions or other fixtures.

def _import(model_name):
    """Dynamically import a Django model."""
    parts = model_name.split('.')
    module_path = '.'.join(parts[:-1])
    model_cls = parts[-1]
    from importlib import import_module
    mod = import_module(module_path)
    return getattr(mod, model_cls)


def create_project(db, name='Test Project', description='Test project description',
                   status='active', manager=None, **kwargs):
    """Create a Project instance."""
    from projects.models import Project
    return Project.objects.create(
        name=name,
        description=description,
        status=status,
        manager=manager,
        **kwargs,
    )


def create_trial(db, title='Test Trial', client='Test Client',
                 description='Test trial description', status='planned',
                 version=0, **kwargs):
    """Create a Trial instance."""
    from events.models import Trial
    return Trial.objects.create(
        title=title,
        client=client,
        description=description,
        status=status,
        version=version,
        **kwargs,
    )


def create_time_slot(db, trial, start_time, end_time, description='', **kwargs):
    """Create a TimeSlot instance."""
    from events.models import TimeSlot
    return TimeSlot.objects.create(
        trial=trial,
        start_time=start_time,
        end_time=end_time,
        description=description,
        **kwargs,
    )


def create_equipment(db, name='Test Equipment', description='Test equipment', **kwargs):
    """Create an Equipment instance."""
    from events.models import Equipment
    return Equipment.objects.create(
        name=name,
        description=description,
        **kwargs,
    )


def create_document_template(db, name='Test Template', template_type='tech_design',
                             content='Template content', owner=None,
                             project=None, variables=None, **kwargs):
    """Create a DocumentTemplate instance."""
    from documents.models import DocumentTemplate
    return DocumentTemplate.objects.create(
        name=name,
        template_type=template_type,
        content=content,
        owner=owner,
        project=project,
        variables=variables or {},
        **kwargs,
    )


def create_generated_document(db, template, content='Generated content',
                              generated_by=None, variables_used=None, **kwargs):
    """Create a GeneratedDocument instance."""
    from documents.models import GeneratedDocument
    return GeneratedDocument.objects.create(
        template=template,
        content=content,
        generated_by=generated_by,
        variables_used=variables_used or {},
        **kwargs,
    )


def create_book(db, title='Test Book', author='Test Author', description='Test book',
                project=None, **kwargs):
    """Create a Book instance."""
    from documents.models import Book
    return Book.objects.create(
        title=title,
        author=author,
        description=description,
        project=project,
        **kwargs,
    )


def create_chapter(db, book, title='Test Chapter', content_md='Chapter content',
                   order=1, **kwargs):
    """Create a Chapter instance."""
    from documents.models import Chapter
    return Chapter.objects.create(
        book=book,
        title=title,
        content_md=content_md,
        order=order,
        **kwargs,
    )


def create_meeting_room(db, name='Test Room', description='Test meeting room',
                        capacity=10, location='Building A', **kwargs):
    """Create a MeetingRoom instance."""
    from meeting_rooms.models import MeetingRoom
    return MeetingRoom.objects.create(
        name=name,
        description=description,
        capacity=capacity,
        location=location,
        **kwargs,
    )


def create_meeting_room_booking(db, meeting_room, user, start_time, end_time,
                                title='Test Booking', participants='',
                                description='Test booking', **kwargs):
    """Create a MeetingRoomBooking instance."""
    from meeting_rooms.models import MeetingRoomBooking
    booking = MeetingRoomBooking(
        meeting_room=meeting_room,
        user=user,
        start_time=start_time,
        end_time=end_time,
        title=title,
        participants=participants,
        description=description,
        **kwargs,
    )
    booking.save()
    return booking


def create_post(db, title='Test Post', content='Test post content',
                author=None, **kwargs):
    """Create a Post instance."""
    from communication.models import Post
    return Post.objects.create(
        title=title,
        content=content,
        author=author,
        **kwargs,
    )


def create_comment(db, post, author, content='Test comment', **kwargs):
    """Create a Comment instance."""
    from communication.models import Comment
    return Comment.objects.create(
        post=post,
        author=author,
        content=content,
        **kwargs,
    )


def create_news_type(db, name='Test News Type', **kwargs):
    """Create a NewsType instance."""
    from news.models import NewsType
    return NewsType.objects.create(
        name=name,
        **kwargs,
    )


def create_news_article(db, title='Test News', link='https://example.com/news',
                        publication_date=None, personnel=None, news_type=None, **kwargs):
    """Create a NewsArticle instance."""
    from datetime import date
    from news.models import NewsArticle
    return NewsArticle.objects.create(
        title=title,
        link=link,
        publication_date=publication_date or date.today(),
        personnel=personnel,
        news_type=news_type,
        **kwargs,
    )


def create_dify_app(db, name='Test Dify App', description='Test app',
                    embed_url='https://example.com/embed/app',
                    is_active=True, **kwargs):
    """Create a DifyApp instance."""
    from dify_apps.models import DifyApp
    return DifyApp.objects.create(
        name=name,
        description=description,
        embed_url=embed_url,
        is_active=is_active,
        **kwargs,
    )


def create_ragflow_config(db, name='Test Ragflow Config',
                          api_endpoint='https://ragflow.example.com/api',
                          api_key='test-api-key', is_active=True, **kwargs):
    """Create a RagflowConfig instance."""
    from ragflow_service.models import RagflowConfig
    return RagflowConfig.objects.create(
        name=name,
        api_endpoint=api_endpoint,
        api_key=api_key,
        is_active=is_active,
        **kwargs,
    )
