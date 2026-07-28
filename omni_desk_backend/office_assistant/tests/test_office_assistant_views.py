"""
Tests for office_assistant module.
"""
import pytest
from rest_framework import status


@pytest.mark.django_db
class TestOfficeAssistantProcessView:
    def test_process_unauthenticated(self, api_client):
        response = api_client.post('/api/office_assistant/process/', {
            'action': 'proofread',
            'text': 'Test text',
        }, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_process_missing_action(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.post('/api/office_assistant/process/', {
            'text': 'Test text',
        }, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_process_missing_text(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.post('/api/office_assistant/process/', {
            'action': 'proofread',
        }, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_process_invalid_action(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.post('/api/office_assistant/process/', {
            'action': 'invalid_action',
            'text': 'Test text',
        }, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Invalid action' in response.data['error']

    def test_process_proofread_mocked(self, api_client, regular_user_obj, mocker):
        """Test proofread action with mocked LLMRouter"""
        api_client.force_authenticate(user=regular_user_obj)
        mock_router = mocker.MagicMock()
        # router.generate 非流式返回 (content, usage) 元组
        mock_router.generate.return_value = ('Corrected text', {})
        mocker.patch('office_assistant.views.get_router', return_value=mock_router)

        response = api_client.post('/api/office_assistant/process/', {
            'action': 'proofread',
            'text': 'Test text with eror',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['processed_text'] == 'Corrected text'

    def test_process_translate_mocked(self, api_client, regular_user_obj, mocker):
        """Test translate action with mocked LLMRouter"""
        api_client.force_authenticate(user=regular_user_obj)
        mock_router = mocker.MagicMock()
        mock_router.generate.return_value = ('翻译后的文本', {})
        mocker.patch('office_assistant.views.get_router', return_value=mock_router)

        response = api_client.post('/api/office_assistant/process/', {
            'action': 'translate',
            'text': 'Text to translate',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert '翻译' in response.data['processed_text']

    def test_process_polish_mocked(self, api_client, regular_user_obj, mocker):
        """Test polish action with mocked LLMRouter"""
        api_client.force_authenticate(user=regular_user_obj)
        mock_router = mocker.MagicMock()
        mock_router.generate.return_value = ('Polished text', {})
        mocker.patch('office_assistant.views.get_router', return_value=mock_router)

        response = api_client.post('/api/office_assistant/process/', {
            'action': 'polish',
            'text': 'Rough text',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['processed_text'] == 'Polished text'

    def test_process_stream_mode(self, api_client, regular_user_obj, mocker):
        """Test streaming mode returns StreamingHttpResponse"""
        api_client.force_authenticate(user=regular_user_obj)
        mock_router = mocker.MagicMock()
        # 流式模式下 router.generate 返回内容分片生成器
        mock_router.generate.return_value = iter(['chunk1', 'chunk2'])
        mocker.patch('office_assistant.views.get_router', return_value=mock_router)

        response = api_client.post('/api/office_assistant/process/', {
            'action': 'proofread',
            'text': 'Test text',
            'stream': True,
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
