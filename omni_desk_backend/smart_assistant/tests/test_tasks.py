"""Tests for smart_assistant Celery tasks."""

from unittest.mock import patch, MagicMock

from django.test import TestCase

from smart_assistant.tasks import process_document_embedding


class TestProcessDocumentEmbedding(TestCase):
    """process_document_embedding Celery 任务测试."""

    @patch('ragflow_service.models.RagflowConfig')
    @patch('smart_assistant.tasks.requests')
    @patch('smart_assistant.tasks.getattr')
    def test_successful_embedding_process(self, mock_getattr, mock_requests, mock_ragflow_config):
        """文档成功上传到 Ragflow 并完成解析."""
        mock_getattr.return_value = 'test-dataset-id'

        mock_config_obj = MagicMock()
        mock_config_obj.api_endpoint = 'http://ragflow:8000'
        mock_config_obj.api_key = 'test-api-key'
        mock_ragflow_config.objects.filter.return_value.first.return_value = mock_config_obj

        mock_upload_response = MagicMock()
        mock_upload_response.raise_for_status.return_value = None
        mock_upload_response.json.return_value = {'data': [{'id': 'ragflow-doc-123'}]}

        mock_parse_response = MagicMock()
        mock_parse_response.raise_for_status.return_value = None

        mock_requests.post.side_effect = [mock_upload_response, mock_parse_response]

        from smart_assistant.models import KnowledgeBaseDocument
        with patch.object(KnowledgeBaseDocument, 'objects') as mock_objects:
            mock_doc = MagicMock()
            mock_objects.get.return_value = mock_doc

            process_document_embedding('doc-1')

        assert mock_doc.embedding_status == 'completed'
        assert mock_doc.ragflow_document_id == 'ragflow-doc-123'
        assert mock_requests.post.call_count == 2

    @patch('smart_assistant.tasks.getattr')
    @patch('ragflow_service.models.RagflowConfig')
    def test_missing_dataset_id_raises_error(self, mock_ragflow_config, mock_getattr):
        """SMART_ASSISTANT_DATASET_ID 未配置时任务失败."""
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from smart_assistant.models import KnowledgeBaseDocument

        # Create a real document so the except block can update it
        f = SimpleUploadedFile('test.txt', b'content', content_type='text/plain')
        doc = KnowledgeBaseDocument.objects.create(title='test', file=f)

        # Mock RagflowConfig so we reach the dataset_id check
        mock_config_obj = MagicMock()
        mock_config_obj.api_endpoint = 'http://ragflow:8000'
        mock_config_obj.api_key = 'test-key'
        mock_ragflow_config.objects.filter.return_value.first.return_value = mock_config_obj

        mock_getattr.return_value = None

        with self.assertRaisesRegex(ValueError, 'SMART_ASSISTANT_DATASET_ID'):
            process_document_embedding(doc.id)

        doc.refresh_from_db()
        self.assertEqual(doc.embedding_status, 'failed')

    @patch('ragflow_service.models.RagflowConfig')
    def test_missing_ragflow_config_raises_error(self, mock_ragflow_config):
        """Ragflow 配置未激活时任务失败."""
        from smart_assistant.models import KnowledgeBaseDocument

        mock_ragflow_config.objects.filter.return_value.first.return_value = None

        with patch.object(KnowledgeBaseDocument, 'objects') as mock_objects:
            mock_doc = MagicMock()
            mock_objects.get.return_value = mock_doc

            with self.assertRaisesRegex(ValueError, 'Ragflow 配置未激活'):
                process_document_embedding('doc-1')

    def test_document_not_found_silently_passes(self):
        """文档不存在时静默通过."""
        from smart_assistant.models import KnowledgeBaseDocument

        with patch.object(KnowledgeBaseDocument, 'objects') as mock_objects:
            mock_objects.get.side_effect = KnowledgeBaseDocument.DoesNotExist
            process_document_embedding('nonexistent-id')

    @patch('ragflow_service.models.RagflowConfig')
    @patch('smart_assistant.tasks.requests')
    @patch('smart_assistant.tasks.getattr')
    def test_upload_failure_marks_as_failed(self, mock_getattr, mock_requests, mock_ragflow_config):
        """上传失败时文档状态标记为 failed."""
        mock_getattr.return_value = 'test-dataset-id'

        mock_config_obj = MagicMock()
        mock_config_obj.api_endpoint = 'http://ragflow:8000'
        mock_config_obj.api_key = 'test-api-key'
        mock_ragflow_config.objects.filter.return_value.first.return_value = mock_config_obj

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'data': []}
        mock_requests.post.return_value = mock_response

        from smart_assistant.models import KnowledgeBaseDocument
        with patch.object(KnowledgeBaseDocument, 'objects') as mock_objects:
            mock_doc = MagicMock()
            mock_objects.get.return_value = mock_doc

            try:
                process_document_embedding('doc-1')
            except ValueError:
                pass

        assert mock_doc.embedding_status == 'failed'
