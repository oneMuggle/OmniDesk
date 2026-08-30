"""Tests for smart_assistant Celery tasks."""

from unittest.mock import patch, MagicMock
from uuid import uuid4

from django.test import TestCase

from smart_assistant.tasks import _notify_agent_task_result, process_document_embedding


class TestAgentTaskResultNotification(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from smart_assistant.models import AgentTask

        self.user = get_user_model().objects.create_user(username="task-notify-user")
        self.task = AgentTask.objects.create(
            task_id=uuid4(),
            user=self.user,
            objective="测试任务",
            task_packet={},
        )

    @patch("smart_assistant.tasks.NotificationService.create")
    def test_notifies_after_terminal_status_with_safe_summary(self, create):
        _notify_agent_task_result(self.task, "failed")

        create.assert_called_once()
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["user"], self.user)
        self.assertEqual(kwargs["type"], "agent_task_result")
        self.assertEqual(kwargs["dedupe_key"], f"agent_task:{self.task.task_id}")
        self.assertIn("失败", kwargs["content"])
        self.assertNotIn("异常原文", kwargs["content"])

    def test_notifies_cancelled_once_when_worker_repeats(self):
        from notifications.models import Notification

        _notify_agent_task_result(self.task, "cancelled")
        _notify_agent_task_result(self.task, "cancelled")

        notifications = Notification.objects.filter(
            user=self.user,
            type="agent_task_result",
            dedupe_key=f"agent_task:{self.task.task_id}",
        )
        self.assertEqual(notifications.count(), 1)
        self.assertIn("取消", notifications.get().content)


class TestAgentTaskTimeouts(TestCase):
    def test_calculate_time_limits_uses_task_budget_and_packet_shape(self):
        from django.test import override_settings
        from smart_assistant.tasks import calculate_agent_task_time_limits

        task = MagicMock(
            global_budget=20000,
            task_packet={
                "subtasks": [{}, {}],
                "final_synthesis": {"objective": "合成"},
                "timeout_seconds": 50,
            },
        )
        with override_settings(
            LLM_REQUEST_TIMEOUT_SECONDS=10,
            AGENT_TASK_RETRY_COEFFICIENT=2,
            AGENT_TASK_MAX_SECONDS=1000,
        ):
            soft, hard = calculate_agent_task_time_limits(task)

        assert soft == 50
        assert hard == 110

    def test_calculate_time_limits_respects_packet_timeout_and_maximum(self):
        from django.test import override_settings
        from smart_assistant.tasks import calculate_agent_task_time_limits

        task = MagicMock(
            global_budget=1000,
            task_packet={
                "subtasks": [{}, {}, {}],
                "timeout_seconds": 700,
            },
        )
        with override_settings(
            LLM_REQUEST_TIMEOUT_SECONDS=100,
            AGENT_TASK_RETRY_COEFFICIENT=2,
            AGENT_TASK_MAX_SECONDS=250,
        ):
            assert calculate_agent_task_time_limits(task) == (250, 310)

    @patch("smart_assistant.tasks.execute_agent_task")
    def test_dispatch_uses_apply_async_with_dynamic_limits(self, mock_task):
        from smart_assistant.tasks import dispatch_agent_task

        task = MagicMock(task_id="task-1", global_budget=1000, task_packet={"subtasks": [{}]})
        dispatch_agent_task(task)

        mock_task.apply_async.assert_called_once()
        assert mock_task.apply_async.call_args.kwargs["args"] == ["task-1"]
        kwargs = mock_task.apply_async.call_args.kwargs
        assert kwargs["time_limit"] > kwargs["soft_time_limit"]

    def test_missing_agent_task_does_not_raise_for_autoretry(self):
        from smart_assistant.models import AgentTask
        from smart_assistant.tasks import execute_agent_task

        with patch.object(AgentTask, "objects") as objects:
            objects.select_for_update.return_value.get.side_effect = AgentTask.DoesNotExist
            assert execute_agent_task.run("missing-task") is None


class TestProcessDocumentEmbedding(TestCase):
    """process_document_embedding Celery 任务测试."""

    @patch('smart_assistant.tasks.RagflowClient')
    @patch('ragflow_service.models.RagflowConfig')
    @patch('smart_assistant.tasks.getattr')
    def test_successful_embedding_process(self, mock_getattr, mock_ragflow_config, mock_ragflow_client_class):
        """文档成功上传到 Ragflow 并完成解析."""
        mock_getattr.return_value = 'test-dataset-id'

        mock_config_obj = MagicMock()
        mock_config_obj.api_endpoint = 'http://ragflow:8000'
        mock_config_obj.api_key = 'test-api-key'
        mock_ragflow_config.objects.filter.return_value.first.return_value = mock_config_obj

        mock_client = MagicMock()
        # upload_document 返回的是 data dict(以列表形式处理)
        mock_client.upload_document.return_value = {'id': 'ragflow-doc-123'}
        mock_client.parse_documents.return_value = True
        mock_ragflow_client_class.return_value = mock_client

        from smart_assistant.models import KnowledgeBaseDocument
        with patch.object(KnowledgeBaseDocument, 'objects') as mock_objects:
            mock_doc = MagicMock()
            mock_objects.get.return_value = mock_doc
            mock_doc.file.open.return_value.__enter__.return_value.read.return_value = b'test content'

            process_document_embedding('doc-1')

        assert mock_doc.embedding_status == 'completed'
        assert mock_doc.ragflow_document_id == 'ragflow-doc-123'
        assert mock_client.upload_document.called
        assert mock_client.parse_documents.called

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

    @patch('smart_assistant.tasks.RagflowClient')
    @patch('ragflow_service.models.RagflowConfig')
    @patch('smart_assistant.tasks.getattr')
    def test_upload_failure_marks_as_failed(self, mock_getattr, mock_ragflow_config, mock_ragflow_client_class):
        """上传失败时文档状态标记为 failed."""
        mock_getattr.return_value = 'test-dataset-id'

        mock_config_obj = MagicMock()
        mock_config_obj.api_endpoint = 'http://ragflow:8000'
        mock_config_obj.api_key = 'test-api-key'
        mock_ragflow_config.objects.filter.return_value.first.return_value = mock_config_obj

        # 模拟 upload_document 返回空数据
        mock_client = MagicMock()
        mock_client.upload_document.return_value = {}  # 返回空,触发 ValueError
        mock_ragflow_client_class.return_value = mock_client

        from smart_assistant.models import KnowledgeBaseDocument
        with patch.object(KnowledgeBaseDocument, 'objects') as mock_objects:
            mock_doc = MagicMock()
            mock_objects.get.return_value = mock_doc
            mock_doc.file.open.return_value.__enter__.return_value.read.return_value = b'test content'

            try:
                process_document_embedding('doc-1')
            except ValueError:
                pass

        assert mock_doc.embedding_status == 'failed'
