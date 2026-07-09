import io
import pytest
import responses
from django.conf import settings
from ..exceptions import (
    PaperlessError, PaperlessUnavailableError, PaperlessAuthError, PaperlessNotFoundError
)
from ..services.client import PaperlessClient


@pytest.fixture
def client(db, settings):
    settings.PAPERLESS_URL = 'http://paperless:8000'
    settings.PAPERLESS_API_TOKEN = 'test-token'
    settings.PAPERLESS_TIMEOUT_SECONDS = 5
    return PaperlessClient()


class TestPaperlessClientToken:
    @responses.activate
    def test_post_token_success(self, client):
        responses.add(
            responses.POST,
            f'{settings.PAPERLESS_URL}/api/token/',
            json={'token': 'abc123'},
            status=200,
        )
        token = client.post_token('alice', 'pwd')
        assert token == 'abc123'

    @responses.activate
    def test_post_token_invalid_raises_auth(self, client):
        responses.add(
            responses.POST,
            f'{settings.PAPERLESS_URL}/api/token/',
            json={'detail': 'No active account'},
            status=400,
        )
        with pytest.raises(PaperlessAuthError):
            client.post_token('alice', 'wrong')


class TestPaperlessClientUpload:
    @responses.activate
    def test_upload_success(self, client):
        responses.add(
            responses.POST,
            f'{settings.PAPERLESS_URL}/api/documents/post_document/',
            json={'id': 100, 'title': 'doc.pdf'},
            status=200,
        )
        file_obj = io.BytesIO(b'fake pdf content')
        result = client.upload(
            file_obj=file_obj,
            filename='doc.pdf',
            title='doc.pdf',
            owner=5,
        )
        assert result['id'] == 100
        assert 'Authorization' in responses.calls[0].request.headers
        assert responses.calls[0].request.headers['Authorization'] == 'Token test-token'

    @responses.activate
    def test_upload_5xx_raises_unavailable(self, client):
        responses.add(
            responses.POST,
            f'{settings.PAPERLESS_URL}/api/documents/post_document/',
            body='Internal Server Error',
            status=500,
        )
        with pytest.raises(PaperlessUnavailableError):
            client.upload(io.BytesIO(b'x'), 'a.pdf', 'a', owner=1)


class TestPaperlessClientSearch:
    @responses.activate
    def test_search_returns_results(self, client):
        responses.add(
            responses.GET,
            f'{settings.PAPERLESS_URL}/api/documents/',
            json={
                'count': 1,
                'next': None,
                'previous': None,
                'results': [{
                    'id': 50,
                    'title': '合同文件',
                    '__search_hit__': {
                        'score': 0.9,
                        'highlights': '这是<span class="match">合同</span>内容',
                        'rank': 0,
                    },
                }],
            },
            status=200,
        )
        results = client.search('合同', page_size=10)
        assert results['count'] == 1
        assert results['results'][0]['id'] == 50
        assert '<span' in results['results'][0]['__search_hit__']['highlights']


class TestPaperlessClientGetUser:
    @responses.activate
    def test_get_user_by_username(self, client):
        responses.add(
            responses.GET,
            f'{settings.PAPERLESS_URL}/api/users/',
            json={
                'count': 1,
                'results': [{'id': 7, 'username': 'alice'}],
            },
            status=200,
        )
        user = client.get_user_by_username('alice')
        assert user['id'] == 7

    @responses.activate
    def test_get_user_not_found_raises(self, client):
        responses.add(
            responses.GET,
            f'{settings.PAPERLESS_URL}/api/users/',
            json={'count': 0, 'results': []},
            status=200,
        )
        with pytest.raises(PaperlessNotFoundError):
            client.get_user_by_username('ghost')