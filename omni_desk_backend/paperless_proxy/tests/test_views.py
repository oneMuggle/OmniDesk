import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
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


# --- Task 15: Download / Preview / SyncStatus ---


@pytest.fixture
def synced_binding(db, user):
    return DocumentBinding.objects.create(
        source_type='project_document', source_id=1, paperless_id=555,
        paperless_checksum='h', owner=user, title='X',
    )


@pytest.mark.django_db
class TestDownloadAPI:
    @patch('paperless_proxy.services.client.PaperlessClient.download')
    def test_download_success(self, mock_dl, user, synced_binding):
        mock_dl.return_value = b'pdf content'
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get(f'/api/paperless/documents/{synced_binding.id}/download/')
        assert resp.status_code == 200
        assert b'pdf content' in resp.content

    def test_download_permission_denied(self, admin, user, synced_binding):
        from django.contrib.auth import get_user_model
        CustomUser = get_user_model()
        u2 = CustomUser.objects.create_user(username='eve', password='p')
        client = APIClient()
        client.force_authenticate(u2)
        resp = client.get(f'/api/paperless/documents/{synced_binding.id}/download/')
        assert resp.status_code == 403

    @patch('paperless_proxy.services.client.PaperlessClient.download')
    def test_download_paperless_down_returns_503(self, mock_dl, user, db):
        from paperless_proxy.exceptions import PaperlessUnavailableError
        mock_dl.side_effect = PaperlessUnavailableError('down')
        # 使用不同 paperless_id 避免前一个测试留下的缓存文件触发降级模式
        binding = DocumentBinding.objects.create(
            source_type='contract', source_id=9999, paperless_id=77777,
            paperless_checksum='h2', owner=user, title='Y',
        )
        client = APIClient()
        client.force_authenticate(user)
        resp = client.get(f'/api/paperless/documents/{binding.id}/download/')
        assert resp.status_code == 503


# --- Task 6: Upload API ---


@pytest.mark.django_db
class TestUploadAPI:
    def test_upload_requires_auth(self, db):
        client = APIClient()
        resp = client.post('/api/paperless/upload/', {})
        assert resp.status_code == 401

    def test_upload_missing_file_returns_400(self, user):
        client = APIClient()
        client.force_authenticate(user)
        resp = client.post('/api/paperless/upload/', {'title': 't', 'source_type': 'contract', 'source_id': 1}, format='multipart')
        assert resp.status_code == 400
        assert 'file' in resp.data['detail']

    def test_upload_invalid_source_type_returns_400(self, user):
        client = APIClient()
        client.force_authenticate(user)
        f = SimpleUploadedFile('test.pdf', b'x', content_type='application/pdf')
        resp = client.post('/api/paperless/upload/', {
            'file': f, 'title': 't', 'source_type': 'invalid', 'source_id': 1,
        }, format='multipart')
        assert resp.status_code == 400

    def test_upload_missing_source_id_returns_400(self, user):
        client = APIClient()
        client.force_authenticate(user)
        f = SimpleUploadedFile('test.pdf', b'x', content_type='application/pdf')
        resp = client.post('/api/paperless/upload/', {
            'file': f, 'title': 't', 'source_type': 'contract',
        }, format='multipart')
        assert resp.status_code == 400
        assert 'source_id' in resp.data['detail']

    def test_upload_invalid_source_id_returns_400(self, user):
        client = APIClient()
        client.force_authenticate(user)
        f = SimpleUploadedFile('test.pdf', b'x', content_type='application/pdf')
        resp = client.post('/api/paperless/upload/', {
            'file': f, 'title': 't', 'source_type': 'contract', 'source_id': 'abc',
        }, format='multipart')
        assert resp.status_code == 400
        assert 'source_id' in resp.data['detail']

    def test_upload_creates_binding_and_outbox(self, user, monkeypatch):
        from ..services.upload import PaperlessUploadService
        mock_queue = MagicMock(
            return_value={'binding_id': 1, 'outbox_id': 1, 'status': 'pending'}
        )
        monkeypatch.setattr(PaperlessUploadService, 'queue_upload', mock_queue)
        client = APIClient()
        client.force_authenticate(user)
        f = SimpleUploadedFile('test.pdf', b'x', content_type='application/pdf')
        resp = client.post('/api/paperless/upload/', {
            'file': f, 'title': 't', 'source_type': 'contract', 'source_id': 1,
        }, format='multipart')
        assert resp.status_code == 201
        assert resp.data['status'] == 'pending'
        assert 'binding_id' in resp.data
        assert 'outbox_id' in resp.data
        # 显式断言 kwargs,防止字段映射回归
        mock_queue.assert_called_once()
        call_kwargs = mock_queue.call_args.kwargs
        assert call_kwargs['filename'] == 'test.pdf'
        assert call_kwargs['title'] == 't'
        assert call_kwargs['source_type'] == 'contract'
        assert call_kwargs['source_id'] == 1
        assert call_kwargs['owner'] == user

    def test_upload_tags_comma_string_coerced_to_list(self, user, monkeypatch):
        """multipart 中 tags 为逗号分隔字符串时,应被强制转为 list"""
        from ..services.upload import PaperlessUploadService
        mock_queue = MagicMock(
            return_value={'binding_id': 1, 'outbox_id': 1, 'status': 'pending'}
        )
        monkeypatch.setattr(PaperlessUploadService, 'queue_upload', mock_queue)
        client = APIClient()
        client.force_authenticate(user)
        f = SimpleUploadedFile('test.pdf', b'x', content_type='application/pdf')
        resp = client.post('/api/paperless/upload/', {
            'file': f, 'title': 't', 'source_type': 'contract', 'source_id': 1,
            'tags': 'tag1,tag2, tag3',
        }, format='multipart')
        assert resp.status_code == 201
        call_kwargs = mock_queue.call_args.kwargs
        assert call_kwargs['tags'] == ['tag1', 'tag2', 'tag3']