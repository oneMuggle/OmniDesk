"""
Tests for ragflow_service module (RagflowConfig CRUD + query action with mock).
"""
import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status


@pytest.mark.django_db
class TestRagflowConfigViewSet:
    def test_list_configs(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get('/api/ragflow-service/configs/')
        assert response.status_code == status.HTTP_200_OK

    def test_create_config(self, admin_client):
        response = admin_client.post('/api/ragflow-service/configs/', {
            'name': 'Test Ragflow',
            'api_endpoint': 'https://ragflow.example.com/api',
            'api_key': 'test-key-123',
        }, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Test Ragflow'

    def test_create_config_unauthorized(self, api_client, regular_user_obj):
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.post('/api/ragflow-service/configs/', {
            'name': 'Unauthorized Config',
            'api_endpoint': 'https://example.com',
            'api_key': 'key',
        }, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_retrieve_config(self, admin_client):
        from ragflow_service.models import RagflowConfig
        config = RagflowConfig.objects.create(
            name='Retrieve Config',
            api_endpoint='https://ragflow.example.com/api',
            api_key='key',
        )
        response = admin_client.get(f'/api/ragflow-service/configs/{config.pk}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Retrieve Config'

    def test_update_config(self, admin_client):
        from ragflow_service.models import RagflowConfig
        config = RagflowConfig.objects.create(
            name='Old Config',
            api_endpoint='https://ragflow.example.com/api',
            api_key='key',
        )
        response = admin_client.patch(f'/api/ragflow-service/configs/{config.pk}/', {
            'name': 'Updated Config',
        }, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Config'

    def test_delete_config(self, admin_client):
        from ragflow_service.models import RagflowConfig
        config = RagflowConfig.objects.create(
            name='To Delete',
            api_endpoint='https://ragflow.example.com/api',
            api_key='key',
        )
        response = admin_client.delete(f'/api/ragflow-service/configs/{config.pk}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_query_config_inactive(self, admin_client):
        from ragflow_service.models import RagflowConfig
        config = RagflowConfig.objects.create(
            name='Inactive Config',
            api_endpoint='https://ragflow.example.com/api',
            api_key='key',
            is_active=False,
        )
        response = admin_client.post(f'/api/ragflow-service/configs/{config.pk}/query/', {
            'question': 'Test question',
        }, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert '未激活' in response.data['detail']

    def test_query_config_no_chat_id(self, admin_client):
        """Test query action when chat_id is not configured."""
        from ragflow_service.models import RagflowConfig
        config = RagflowConfig.objects.create(
            name='No Chat ID Config',
            api_endpoint='https://ragflow.example.com/api',
            api_key='key',
            is_active=True,
            chat_id=None,  # No chat_id configured
        )
        response = admin_client.post(f'/api/ragflow-service/configs/{config.pk}/query/', {
            'question': 'Test question',
        }, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Chat Assistant ID' in response.data['detail']

    def test_query_config_active_mocked(self, admin_client):
        """Test query action with mocked RagflowClient."""
        from ragflow_service.models import RagflowConfig
        config = RagflowConfig.objects.create(
            name='Active Config',
            api_endpoint='https://ragflow.example.com/api',
            api_key='key',
            is_active=True,
            chat_id='test-chat-id',
        )

        mock_client = MagicMock()
        mock_client.chat_completion.return_value = {'answer': 'Mocked answer'}

        with patch('ragflow_service.views.RagflowClient', return_value=mock_client):
            response = admin_client.post(f'/api/ragflow-service/configs/{config.pk}/query/', {
                'question': 'Test question',
            }, format='json')
            assert response.status_code == status.HTTP_200_OK
            assert response.data['answer'] == 'Mocked answer'

    def test_query_missing_question(self, admin_client):
        from ragflow_service.models import RagflowConfig
        config = RagflowConfig.objects.create(
            name='Active Config 2',
            api_endpoint='https://ragflow.example.com/api',
            api_key='key',
            is_active=True,
            chat_id='test-chat-id',
        )
        response = admin_client.post(f'/api/ragflow-service/configs/{config.pk}/query/', {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert '缺少' in response.data['detail']

    def test_health_check_success(self, admin_client):
        """Test health_check action with successful connection."""
        from ragflow_service.models import RagflowConfig
        config = RagflowConfig.objects.create(
            name='Health Check Config',
            api_endpoint='https://ragflow.example.com/api',
            api_key='key',
            is_active=True,
        )

        mock_client = MagicMock()
        mock_client.health_check.return_value = {'status': 'ok', 'message': '连接成功'}

        with patch('ragflow_service.views.RagflowClient', return_value=mock_client):
            response = admin_client.get(f'/api/ragflow-service/configs/{config.pk}/health_check/')
            assert response.status_code == status.HTTP_200_OK
            assert response.data['status'] == 'ok'

    def test_health_check_failure(self, admin_client):
        """Test health_check action with failed connection."""
        from ragflow_service.models import RagflowConfig
        config = RagflowConfig.objects.create(
            name='Health Check Fail Config',
            api_endpoint='https://ragflow.example.com/api',
            api_key='key',
            is_active=True,
        )

        mock_client = MagicMock()
        mock_client.health_check.return_value = {'status': 'error', 'message': '连接失败'}

        with patch('ragflow_service.views.RagflowClient', return_value=mock_client):
            response = admin_client.get(f'/api/ragflow-service/configs/{config.pk}/health_check/')
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert response.data['status'] == 'error'
