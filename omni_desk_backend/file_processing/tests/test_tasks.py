import pytest
from unittest.mock import patch, Mock
from django.core.files.uploadedfile import SimpleUploadedFile
from file_processing.tasks import process_file_task
from file_processing.models import UploadedFile
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestProcessFileTask:

    def test_process_file_task_success(self):
        user = User.objects.create_user(username='test', password='test')

        # 读取测试文件
        with open('tests/fixtures/simple.xlsx', 'rb') as f:
            file_content = f.read()

        uploaded_file = SimpleUploadedFile(
            "test.xlsx",
            file_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='test.xlsx',
            file=uploaded_file,
            file_size=len(file_content),
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        # 直接调用任务（不使用 Celery）
        process_file_task(str(uploaded.id))

        # 验证状态更新
        uploaded.refresh_from_db()
        assert uploaded.status == 'completed'
        assert uploaded.sheet_count > 0
        assert hasattr(uploaded, 'result')

    @patch('file_processing.tasks.FileProcessingService')
    def test_process_file_task_failure(self, mock_service_class):
        user = User.objects.create_user(username='test', password='test')

        with open('tests/fixtures/simple.xlsx', 'rb') as f:
            file_content = f.read()

        uploaded_file = SimpleUploadedFile(
            "test.xlsx",
            file_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='test.xlsx',
            file=uploaded_file,
            file_size=len(file_content),
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        # Mock 服务抛出异常
        mock_service = Mock()
        mock_service.process_file.side_effect = Exception("处理失败")
        mock_service_class.return_value = mock_service

        # 调用任务
        with pytest.raises(Exception):
            process_file_task(str(uploaded.id))

        # 验证状态更新为 failed
        uploaded.refresh_from_db()
        assert uploaded.status == 'failed'
        assert '处理失败' in uploaded.error_message

    def test_process_file_task_status_updates(self):
        user = User.objects.create_user(username='test', password='test')

        with open('tests/fixtures/simple.xlsx', 'rb') as f:
            file_content = f.read()

        uploaded_file = SimpleUploadedFile(
            "test.xlsx",
            file_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='test.xlsx',
            file=uploaded_file,
            file_size=len(file_content),
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        # 初始状态
        assert uploaded.status == 'pending'

        # 处理文件
        process_file_task(str(uploaded.id))

        # 最终状态
        uploaded.refresh_from_db()
        assert uploaded.status == 'completed'
