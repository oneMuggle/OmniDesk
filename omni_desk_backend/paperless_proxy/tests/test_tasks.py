import io
import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from ..models import OutboxItem, DocumentBinding
from ..tasks import process_paperless_outbox
from ..services.outbox import OutboxDeadError

CustomUser = get_user_model()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='u', password='p')


@pytest.fixture
def binding(db, user):
    return DocumentBinding.objects.create(
        source_type='project_document', source_id=1,
        paperless_id=0, paperless_checksum='', owner=user, title='X',
    )


@pytest.fixture
def outbox_item(db, user, binding):
    return OutboxItem.objects.create(
        operation='upload',
        status='pending',
        payload={'file_path': '/tmp/fake.pdf', 'filename': 'f.pdf', 'title': 'f.pdf', 'owner': 1},
        binding=binding,
        created_by=user,
    )


@pytest.mark.django_db
class TestOutboxWorker:
    @patch('paperless_proxy.services.outbox.OutboxService.fetch_pending')
    def test_no_pending_no_op(self, mock_fetch):
        """验证:无 pending 时无操作"""
        mock_fetch.return_value = []
        result = process_paperless_outbox()
        assert result == {'processed': 0, 'succeeded': 0, 'failed': 0}

    @patch('paperless_proxy.services.client.PaperlessClient.upload')
    @patch('paperless_proxy.services.outbox.OutboxService.fetch_pending')
    def test_upload_success(self, mock_fetch, mock_upload, outbox_item):
        """验证:成功上传时 status=synced"""
        mock_fetch.return_value = [outbox_item]
        mock_upload.return_value = {'id': 555, 'title': 'f.pdf'}
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b'fake'
            with patch('os.path.exists', return_value=True):
                result = process_paperless_outbox()
        assert result['succeeded'] == 1
        outbox_item.refresh_from_db()
        assert outbox_item.status == 'synced'
        binding = outbox_item.binding
        binding.refresh_from_db()
        assert binding.paperless_id == 555
