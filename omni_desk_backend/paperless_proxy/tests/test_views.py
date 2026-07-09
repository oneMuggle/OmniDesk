import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from ..models import OutboxItem, DocumentBinding

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