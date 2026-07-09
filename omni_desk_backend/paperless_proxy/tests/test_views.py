import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from ..models import OutboxItem, DocumentBinding, PaperlessHealth, UserPaperlessBinding
from ..services.client import PaperlessClient

CustomUser = get_user_model()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='u', password='p')


@pytest.fixture
def admin(db):
    return CustomUser.objects.create_superuser(username='admin', password='admin')


@pytest.fixture
def binding(db, user):
    return DocumentBinding.objects.create(
        source_type='contract', source_id=1, paperless_id=999,
        paperless_checksum='h', owner=user, title='X',
    )


@pytest.fixture
def dead_outbox(db, user, binding):
    return OutboxItem.objects.create(
        operation='upload', status='dead', payload={}, binding=binding,
        created_by=user, retry_count=10,
    )


@pytest.mark.django_db
class TestOutboxListAPI:
    def test_list_requires_admin(self, user, dead_outbox):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get('/api/paperless/outbox/')
        assert resp.status_code == 403

    def test_admin_can_list(self, admin, dead_outbox):
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.get('/api/paperless/outbox/')
        assert resp.status_code == 200
        assert len(resp.data['results']) >= 1

    def test_filter_by_status(self, admin, dead_outbox):
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.get('/api/paperless/outbox/?status=dead')
        assert resp.status_code == 200
        for item in resp.data['results']:
            assert item['status'] == 'dead'


@pytest.mark.django_db
class TestOutboxRetryAPI:
    def test_retry_dead(self, admin, dead_outbox):
        client = APIClient()
        client.force_authenticate(admin)
        resp = client.post(f'/api/paperless/outbox/{dead_outbox.id}/retry/')
        assert resp.status_code == 200
        dead_outbox.refresh_from_db()
        assert dead_outbox.status == 'pending'
        assert dead_outbox.retry_count == 0


@pytest.mark.django_db
class TestHealthAPI:
    def test_health_endpoint(self, user):
        PaperlessHealth.objects.create(is_healthy=True, consecutive_failures=0)
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get('/api/paperless/health/')
        assert resp.status_code == 200
        assert resp.data['is_healthy'] is True


@pytest.mark.django_db
class TestBindAPI:
    @patch.object(PaperlessClient, 'post_token')
    @patch.object(PaperlessClient, 'get_user_by_username')
    def test_bind_success(self, mock_get_user, mock_token, user):
        mock_token.return_value = 'tok'
        mock_get_user.return_value = {'id': 7, 'username': 'alice'}
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/api/paperless/bind/', {
            'username': 'alice', 'password': 'pwd',
        }, format='json')
        assert resp.status_code == 201
        bind = UserPaperlessBinding.objects.get(user=user)
        assert bind.paperless_user_id == 7

    @patch.object(PaperlessClient, 'post_token')
    def test_bind_auth_failure_401(self, mock_token, user):
        from paperless_proxy.exceptions import PaperlessAuthError
        mock_token.side_effect = PaperlessAuthError('invalid')
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/api/paperless/bind/', {
            'username': 'alice', 'password': 'wrong',
        }, format='json')
        assert resp.status_code == 401

    def test_unbind(self, user):
        UserPaperlessBinding.objects.create(
            user=user, paperless_user_id=5, paperless_username='alice'
        )
        client = APIClient()
        client.force_authenticate(user)
        resp = client.delete('/api/paperless/bind/')
        assert resp.status_code == 204
        assert not UserPaperlessBinding.objects.filter(user=user).exists()

    def test_bind_status(self, user):
        UserPaperlessBinding.objects.create(
            user=user, paperless_user_id=5, paperless_username='alice'
        )
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get('/api/paperless/bind/status/')
        assert resp.status_code == 200
        assert resp.data['paperless_username'] == 'alice'