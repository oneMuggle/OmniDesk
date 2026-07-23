import pytest
from unittest.mock import patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from file_processing.models import UploadedFile, ProcessingResult
from django.contrib.auth import get_user_model

User = get_user_model()

FIXTURE_PATH = 'tests/fixtures/simple.xlsx'


def _read_fixture():
    with open(FIXTURE_PATH, 'rb') as f:
        return f.read()


def _create_user(username='testuser', password='testpass'):
    return User.objects.create_user(username=username, password=password)


def _auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _create_processed_file(user):
    """Create a file and process it synchronously (no Celery)."""
    file_content = _read_fixture()
    uploaded_file = SimpleUploadedFile(
        "test.xlsx", file_content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    uploaded = UploadedFile.objects.create(
        user=user,
        original_filename='test.xlsx',
        file=uploaded_file,
        file_size=len(file_content),
        mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    from file_processing.tasks import process_file_task
    process_file_task(str(uploaded.id))
    uploaded.refresh_from_db()
    return uploaded


# =============================================================================
# Upload API
# =============================================================================

@pytest.mark.django_db
class TestFileUploadAPI:

    @patch('file_processing.views.process_file_task')
    def test_upload_file_success(self, mock_task):
        mock_task.delay = MagicMock()
        user = _create_user()
        client = _auth_client(user)
        file_content = _read_fixture()
        file = SimpleUploadedFile(
            "test.xlsx", file_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        response = client.post('/api/file/upload/', {'file': file}, format='multipart')

        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data
        assert response.data['status'] == 'pending'

        uploaded = UploadedFile.objects.get(id=response.data['id'])
        assert uploaded.user == user
        assert uploaded.original_filename == 'test.xlsx'
        mock_task.delay.assert_called_once()

    def test_upload_file_unauthenticated(self):
        file_content = _read_fixture()
        file = SimpleUploadedFile(
            "test.xlsx", file_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        client = APIClient()
        response = client.post('/api/file/upload/', {'file': file}, format='multipart')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('file_processing.views.process_file_task')
    def test_upload_no_file_returns_400(self, mock_task):
        user = _create_user()
        client = _auth_client(user)
        response = client.post('/api/file/upload/', {}, format='multipart')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# Preview API
# =============================================================================

@pytest.mark.django_db
class TestFilePreviewAPI:

    def test_get_preview_completed(self):
        user = _create_user()
        client = _auth_client(user)
        uploaded = _create_processed_file(user)

        response = client.get(f'/api/file/{uploaded.id}/preview/')

        assert response.status_code == status.HTTP_200_OK
        assert 'sheets' in response.data
        assert 'markdown' in response.data
        assert response.data['file_id'] == str(uploaded.id)

    def test_preview_pending_file(self):
        user = _create_user()
        client = _auth_client(user)
        file_content = _read_fixture()
        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='pending.xlsx',
            file=SimpleUploadedFile("pending.xlsx", file_content,
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            file_size=len(file_content),
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = client.get(f'/api/file/{uploaded.id}/preview/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data.get('status') == 'pending'

    def test_preview_other_user_file_forbidden(self):
        owner = _create_user(username='owner')
        other = _create_user(username='other')
        client = _auth_client(other)
        uploaded = _create_processed_file(owner)

        response = client.get(f'/api/file/{uploaded.id}/preview/')

        assert response.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# Analyze API
# =============================================================================

@pytest.mark.django_db
class TestFileAnalyzeAPI:

    def test_analyze_completed_file(self):
        user = _create_user()
        client = _auth_client(user)
        uploaded = _create_processed_file(user)

        response = client.post(f'/api/file/{uploaded.id}/analyze/')

        assert response.status_code == status.HTTP_200_OK
        assert 'summary' in response.data
        assert 'analysis_id' in response.data

    def test_analyze_pending_file_returns_400(self):
        user = _create_user()
        client = _auth_client(user)
        file_content = _read_fixture()
        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='pending.xlsx',
            file=SimpleUploadedFile("pending.xlsx", file_content,
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            file_size=len(file_content),
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = client.post(f'/api/file/{uploaded.id}/analyze/')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# Query API
# =============================================================================

@pytest.mark.django_db
class TestFileQueryAPI:

    @patch('file_processing.views.NaturalLanguageQuery')
    def test_query_success(self, mock_nl_class):
        mock_nl = MagicMock()
        mock_nl.query.return_value = '测试回答'
        mock_nl_class.return_value = mock_nl

        user = _create_user()
        client = _auth_client(user)
        uploaded = _create_processed_file(user)

        response = client.post(f'/api/file/{uploaded.id}/query/',
                               {'question': '数据有多少行?'}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['answer'] == '测试回答'
        assert response.data['question'] == '数据有多少行?'
        mock_nl.query.assert_called_once()

    def test_query_no_question_returns_400(self):
        user = _create_user()
        client = _auth_client(user)
        uploaded = _create_processed_file(user)

        response = client.post(f'/api/file/{uploaded.id}/query/', {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# Export API
# =============================================================================

@pytest.mark.django_db
class TestFileExportAPI:

    def test_export_csv(self):
        user = _create_user()
        client = _auth_client(user)
        uploaded = _create_processed_file(user)

        response = client.get(f'/api/file/{uploaded.id}/export/csv/')

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'text/csv'

    def test_export_markdown(self):
        user = _create_user()
        client = _auth_client(user)
        uploaded = _create_processed_file(user)

        response = client.get(f'/api/file/{uploaded.id}/export/markdown/')

        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'text/markdown'

    def test_export_unsupported_format(self):
        user = _create_user()
        client = _auth_client(user)
        uploaded = _create_processed_file(user)

        response = client.get(f'/api/file/{uploaded.id}/export/json/')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_export_pending_file_returns_400(self):
        user = _create_user()
        client = _auth_client(user)
        file_content = _read_fixture()
        uploaded = UploadedFile.objects.create(
            user=user,
            original_filename='pending.xlsx',
            file=SimpleUploadedFile("pending.xlsx", file_content,
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            file_size=len(file_content),
            mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = client.get(f'/api/file/{uploaded.id}/export/csv/')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
