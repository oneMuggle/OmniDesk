import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from file_processing.models import UploadedFile, ProcessingResult, AIAnalysis
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUploadedFile:

    def test_create_uploaded_file(self):
        user = User.objects.create_user(username='test', password='test')
        file = SimpleUploadedFile("test.xlsx", b"file content")

        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='test.xlsx',
            file=file,
            file_size=12,
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        assert uploaded.status == 'pending'
        assert uploaded.original_filename == 'test.xlsx'
        assert uploaded.user == user


@pytest.mark.django_db
class TestProcessingResult:

    def test_create_processing_result(self):
        user = User.objects.create_user(username='test', password='test')
        file = SimpleUploadedFile("test.xlsx", b"file content")
        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='test.xlsx',
            file=file,
            file_size=12,
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        result = ProcessingResult.objects.create(
            file=uploaded,
            content_text='test content',
            content_markdown='# test',
            row_count=10,
            column_count=5
        )

        assert result.file == uploaded
        assert result.row_count == 10
        assert uploaded.result == result


@pytest.mark.django_db
class TestAIAnalysis:

    def test_create_ai_analysis(self):
        user = User.objects.create_user(username='test', password='test')
        file = SimpleUploadedFile("test.xlsx", b"file content")
        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='test.xlsx',
            file=file,
            file_size=12,
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        analysis = AIAnalysis.objects.create(
            file=uploaded,
            analysis_type='summary',
            result_text='共 10 行数据',
            result_data={'row_count': 10}
        )

        assert analysis.file == uploaded
        assert analysis.analysis_type == 'summary'
        assert uploaded.analyses.count() == 1
