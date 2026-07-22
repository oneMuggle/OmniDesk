import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from file_processing.services import FileProcessingService
from file_processing.models import UploadedFile
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestFileProcessingService:

    def test_process_excel_file(self):
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

        service = FileProcessingService()
        result = service.process_file(uploaded)

        assert result is not None
        assert result.content_text != ''
        assert result.content_markdown != ''
        assert result.row_count == 3
        assert uploaded.status == 'completed'

    def test_get_processor_excel(self):
        service = FileProcessingService()
        processor = service.get_processor('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        assert processor.__class__.__name__ == 'ExcelProcessor'

    def test_get_processor_word(self):
        service = FileProcessingService()
        processor = service.get_processor('application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        assert processor.__class__.__name__ == 'WordProcessor'

    def test_get_processor_pdf(self):
        service = FileProcessingService()
        processor = service.get_processor('application/pdf')
        assert processor.__class__.__name__ == 'PDFProcessor'

    def test_get_processor_unsupported(self):
        service = FileProcessingService()
        with pytest.raises(ValueError, match="不支持的文件类型"):
            service.get_processor('application/unknown')
