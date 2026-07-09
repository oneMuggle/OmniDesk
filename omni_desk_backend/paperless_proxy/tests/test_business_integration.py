import os
import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from ..models import DocumentBinding, OutboxItem, UserPaperlessBinding
from ..services.upload import PaperlessUploadService

CustomUser = get_user_model()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='alice', password='pwd')


@pytest.mark.django_db
class TestUploadService:
    @patch('paperless_proxy.services.client.PaperlessClient.upload')
    def test_queue_upload_creates_outbox(self, mock_upload, user):
        """验证:queue_upload 创建 DocumentBinding + OutboxItem"""
        mock_upload.return_value = {'id': 999, 'checksum': 'h'}
        UserPaperlessBinding.objects.create(
            user=user, paperless_user_id=5, paperless_username='alice'
        )
        file = SimpleUploadedFile('test.pdf', b'fake content', content_type='application/pdf')
        result = PaperlessUploadService.queue_upload(
            file=file,
            filename='test.pdf',
            title='测试文档',
            source_type='project_document',
            source_id=42,
            owner=user,
        )
        assert result['status'] == 'pending'
        assert result['binding_id']
        assert result['outbox_id']

        binding = DocumentBinding.objects.get(id=result['binding_id'])
        assert binding.paperless_id == 0
        assert binding.paperless_checksum == ''
        assert binding.source_type == 'project_document'
        assert binding.source_id == 42
        assert binding.owner == user
        assert binding.title == '测试文档'

        outbox = OutboxItem.objects.get(id=result['outbox_id'])
        assert outbox.operation == 'upload'
        assert outbox.status == 'pending'
        assert outbox.binding == binding
        assert outbox.created_by == user
        assert outbox.payload['filename'] == 'test.pdf'
        assert outbox.payload['title'] == '测试文档'
        assert outbox.payload['owner'] == 5
        assert os.path.exists(outbox.payload['file_path'])
        with open(outbox.payload['file_path'], 'rb') as saved_file:
            assert saved_file.read() == b'fake content'
        mock_upload.assert_not_called()
