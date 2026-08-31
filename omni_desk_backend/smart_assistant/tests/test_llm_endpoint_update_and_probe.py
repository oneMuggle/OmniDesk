"""LLM 端点管理回归测试(修复分支 fix/llm-endpoint-update-test).

对应三个已确认缺陷:
1. api_endpoint 以 /v1 结尾时,test-endpoint / fetch-models 拼出 /v1/v1/models
2. 编辑端点时空 api_key(前端语义为"留空则不修改")被序列化器拒绝 → 400
3. 创建/更新接口响应中回显解密后的 api_key 明文
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser
from smart_assistant.models import LlmEndpoint


class LlmEndpointUrlNormalizationTests(TestCase):
    """api_endpoint 以 /v1 结尾时不应拼出 /v1/v1/models."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='admin', password='admin123', is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.endpoint = LlmEndpoint.objects.create(
            name="带v1端点", api_endpoint="https://93.184.216.34/v1",
            api_key="sk-test",
        )

    @patch('smart_assistant.views.llm_config.http_requests.get')
    def test_test_endpoint_strips_trailing_v1(self, mock_get):
        """test-endpoint: 地址末尾的 /v1 应被剥掉,只拼一次 /v1/models."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "m-1"}]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        response = self.client.post(
            f'/api/smart-assistant/endpoints/{self.endpoint.id}/test-endpoint/',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        called_url = mock_get.call_args[0][0]
        self.assertEqual(called_url, "https://93.184.216.34/v1/models")

    @patch('smart_assistant.views.llm_config.http_requests.get')
    def test_fetch_models_strips_trailing_v1(self, mock_get):
        """fetch-models: 同样剥掉末尾 /v1."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "m-1"}]}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        response = self.client.post(
            f'/api/smart-assistant/endpoints/{self.endpoint.id}/fetch-models/',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        called_url = mock_get.call_args[0][0]
        self.assertEqual(called_url, "https://93.184.216.34/v1/models")

    @patch('smart_assistant.views.llm_config.http_requests.get')
    def test_plain_base_url_still_appends_v1(self, mock_get):
        """不带 /v1 的基础地址行为不变(仍拼 /v1/models)."""
        plain = LlmEndpoint.objects.create(
            name="普通端点", api_endpoint="https://93.184.216.34",
            api_key="sk-test",
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        response = self.client.post(
            f'/api/smart-assistant/endpoints/{plain.id}/test-endpoint/',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        called_url = mock_get.call_args[0][0]
        self.assertEqual(called_url, "https://93.184.216.34/v1/models")

    @patch('smart_assistant.views.llm_config.http_requests.get')
    def test_v1_variants_and_full_models_url_are_normalized(self, mock_get):
        """大小写/尾斜杠和用户误粘贴完整 models URL 都只请求一次路径."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        for url in (
            "https://93.184.216.34/v1/",
            "https://93.184.216.34/V1",
            "https://93.184.216.34/v1/models",
        ):
            endpoint = LlmEndpoint.objects.create(
                name=url, api_endpoint=url, api_key="sk-test",
            )
            response = self.client.post(
                f'/api/smart-assistant/endpoints/{endpoint.id}/test-endpoint/',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(mock_get.call_args[0][0], "https://93.184.216.34/v1/models")

            mock_get.reset_mock()


class LlmEndpointUpdateEmptyKeyTests(TestCase):
    """编辑端点时空 api_key 应表示"保持不变",而非校验失败."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='admin', password='admin123', is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.endpoint = LlmEndpoint.objects.create(
            name="原端点", api_endpoint="https://old.api.com",
            api_key="sk-original-key",
        )

    def test_put_with_empty_api_key_keeps_original(self):
        """PUT(前端编辑表单完整提交)空 api_key → 200 且密钥不变."""
        response = self.client.put(
            f'/api/smart-assistant/endpoints/{self.endpoint.id}/',
            {
                'name': '改名',
                'api_endpoint': 'https://new.api.com',
                'is_active': True,
                'priority': 2,
                'is_fallback': False,
                'model_capabilities': [],
                'cost_per_1k_tokens': None,
                'api_key': '',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.api_key, "sk-original-key")
        self.assertEqual(self.endpoint.name, "改名")
        self.assertEqual(self.endpoint.api_endpoint, "https://new.api.com")

    def test_patch_with_empty_api_key_keeps_original(self):
        """PATCH 空 api_key → 200 且密钥不变."""
        response = self.client.patch(
            f'/api/smart-assistant/endpoints/{self.endpoint.id}/',
            {'name': '仅改名', 'api_key': ''},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.api_key, "sk-original-key")

    def test_patch_with_new_api_key_updates(self):
        """提供非空 api_key 时仍正常替换."""
        response = self.client.patch(
            f'/api/smart-assistant/endpoints/{self.endpoint.id}/',
            {'api_key': 'sk-rotated'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.api_key, "sk-rotated")


class LlmEndpointKeyNotEchoedTests(TestCase):
    """创建/更新响应不得回显 api_key 明文."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='admin', password='admin123', is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_response_does_not_echo_api_key(self):
        response = self.client.post(
            '/api/smart-assistant/endpoints/',
            {
                'name': '新端点',
                'api_endpoint': 'https://secret.api.com',
                'api_key': 'sk-super-secret',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertNotIn('api_key', response.data)

    def test_create_rejects_api_key_longer_than_model_limit(self):
        """超长密钥在 API 层返回 400,而不是触发数据库 DataError/500."""
        response = self.client.post(
            '/api/smart-assistant/endpoints/',
            {
                'name': '超长密钥端点',
                'api_endpoint': 'https://secret.api.com',
                'api_key': 'x' * 501,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('api_key', response.data)

    def test_update_response_does_not_echo_api_key(self):
        endpoint = LlmEndpoint.objects.create(
            name="旧端点", api_endpoint="https://old.api.com",
            api_key="sk-old-secret",
        )
        response = self.client.patch(
            f'/api/smart-assistant/endpoints/{endpoint.id}/',
            {'name': '改名', 'api_key': 'sk-new-secret'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertNotIn('api_key', response.data)
