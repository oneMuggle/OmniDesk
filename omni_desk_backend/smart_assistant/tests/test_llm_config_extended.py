"""LlmEndpointViewSet / LlmAppConfigViewSet 扩展测试.

对应交接文档任务 A.2 / 计划阶段 2.3:
- 端点 CRUD
- 激活端点切换(自动取消其他 is_active)
- fetch-models 健康检查
- test-endpoint 健康检查(超时/连接错/认证错)
- AppConfig CRUD + 同 app_name 互斥激活
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser
from smart_assistant.models import LlmEndpoint, LlmAppConfig


class TestLlmEndpointCRUD(TestCase):
    """LlmEndpointViewSet 端点 CRUD 测试."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='admin', password='admin123', is_staff=True, is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_endpoints(self):
        """GET /llm-endpoints/ 返回端点列表."""
        LlmEndpoint.objects.create(
            name="主端点", api_endpoint="https://api.openai.com",
            api_key="sk-xxx",
        )
        LlmEndpoint.objects.create(
            name="备用端点", api_endpoint="https://api.anthropic.com",
            api_key="sk-yyy", is_fallback=True,
        )

        response = self.client.get('/api/smart-assistant/endpoints/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_create_endpoint_activates_and_deactivates_others(self):
        """创建 is_active=True 端点,自动取消其他端点的 is_active."""
        old = LlmEndpoint.objects.create(
            name="旧端点", api_endpoint="https://old.api.com",
            api_key="sk-old", is_active=True,
        )

        response = self.client.post(
            '/api/smart-assistant/endpoints/',
            {
                'name': '新端点',
                'api_endpoint': 'https://new.api.com',
                'api_key': 'sk-new',
                'is_active': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 旧端点应被取消
        old.refresh_from_db()
        self.assertFalse(old.is_active, "创建新 active 端点时,旧 active 端点应自动取消")
        # 新端点 active
        new = LlmEndpoint.objects.get(name='新端点')
        self.assertTrue(new.is_active)

    def test_create_inactive_endpoint_does_not_affect_others(self):
        """创建 is_active=False 端点,不影响其他端点状态."""
        old = LlmEndpoint.objects.create(
            name="旧端点", api_endpoint="https://old.api.com",
            api_key="sk-old", is_active=True,
        )

        response = self.client.post(
            '/api/smart-assistant/endpoints/',
            {
                'name': '非活跃端点',
                'api_endpoint': 'https://inactive.api.com',
                'api_key': 'sk-inactive',
                'is_active': False,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 旧端点保持 active
        old.refresh_from_db()
        self.assertTrue(old.is_active)

    def test_update_endpoint_activates_and_deactivates_others(self):
        """PUT/PATCH 更新为 is_active=True,自动取消其他端点."""
        old = LlmEndpoint.objects.create(
            name="旧端点", api_endpoint="https://old.api.com",
            api_key="sk-old", is_active=True,
        )
        new = LlmEndpoint.objects.create(
            name="新端点", api_endpoint="https://new.api.com",
            api_key="sk-new", is_active=False,
        )

        # 更新 new 为 active
        response = self.client.patch(
            f'/api/smart-assistant/endpoints/{new.id}/',
            {'is_active': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        old.refresh_from_db()
        self.assertFalse(old.is_active, "更新端点为 active 时,旧 active 端点应自动取消")
        new.refresh_from_db()
        self.assertTrue(new.is_active)


class TestLlmEndpointFetchModels(TestCase):
    """LlmEndpointViewSet fetch-models 端点测试."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='admin', password='admin123', is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.endpoint = LlmEndpoint.objects.create(
            name="测试端点", api_endpoint="https://93.184.216.34",
            api_key="sk-test",
        )

    @patch('smart_assistant.views.llm_config.http_requests.get')
    def test_fetch_models_success(self, mock_get):
        """fetch-models 成功:200 + 模型列表."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-4"},
                {"id": "gpt-3.5-turbo"},
                {"id": "claude-3-opus"},
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        response = self.client.post(
            f'/api/smart-assistant/endpoints/{self.endpoint.id}/fetch-models/',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        # 应按字母序排序
        self.assertEqual(
            response.data['models'],
            ['claude-3-opus', 'gpt-3.5-turbo', 'gpt-4'],
        )
        # 验证请求 URL 和 headers
        mock_get.assert_called_once()
        called_url = mock_get.call_args[0][0]
        self.assertEqual(called_url, "https://93.184.216.34/v1/models")
        called_headers = mock_get.call_args.kwargs['headers']
        self.assertIn('Authorization', called_headers)

    @patch('smart_assistant.views.llm_config.http_requests.get')
    def test_fetch_models_timeout(self, mock_get):
        """fetch-models 超时:504."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("连接超时")

        response = self.client.post(
            f'/api/smart-assistant/endpoints/{self.endpoint.id}/fetch-models/',
        )

        self.assertEqual(response.status_code, status.HTTP_504_GATEWAY_TIMEOUT)
        self.assertIn('error', response.data)
        self.assertIn('超时', response.data['error'])

    @patch('smart_assistant.views.llm_config.http_requests.get')
    def test_fetch_models_connection_error(self, mock_get):
        """fetch-models 连接错误:502."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("无法连接")

        response = self.client.post(
            f'/api/smart-assistant/endpoints/{self.endpoint.id}/fetch-models/',
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn('error', response.data)


class TestLlmEndpointTestEndpoint(TestCase):
    """LlmEndpointViewSet test-endpoint 端点测试."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='admin', password='admin123', is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.endpoint = LlmEndpoint.objects.create(
            name="测试端点", api_endpoint="https://93.184.216.34",
            api_key="sk-test",
        )

    @patch('smart_assistant.views.llm_config.http_requests.get')
    def test_test_endpoint_success(self, mock_get):
        """test-endpoint 成功:200 + model_count."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "model-1"},
                {"id": "model-2"},
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        response = self.client.post(
            f'/api/smart-assistant/endpoints/{self.endpoint.id}/test-endpoint/',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')
        self.assertEqual(response.data['model_count'], 2)
        self.assertIn('端点连接正常', response.data['message'])

    @patch('smart_assistant.views.llm_config.http_requests.get')
    def test_test_endpoint_auth_error_401(self, mock_get):
        """test-endpoint 401 认证错误."""
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API key"
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_get.side_effect = http_error

        response = self.client.post(
            f'/api/smart-assistant/endpoints/{self.endpoint.id}/test-endpoint/',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['status'], 'auth_error')
        self.assertIn('认证失败', response.data['message'])


class TestLlmAppConfigCRUD(TestCase):
    """LlmAppConfigViewSet 应用配置测试."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='admin', password='admin123', is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.endpoint = LlmEndpoint.objects.create(
            name="主端点", api_endpoint="https://93.184.216.34",
            api_key="sk-test",
        )

    def test_list_app_configs(self):
        """GET /llm-app-configs/ 返回列表,包含 endpoint_name/api_endpoint 冗余字段."""
        LlmAppConfig.objects.create(
            app_name="smart_assistant", endpoint=self.endpoint,
            model_name="gpt-4", is_active=True,
        )

        response = self.client.get('/api/smart-assistant/app-configs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        config = response.data['results'][0]
        # 验证冗余字段
        self.assertEqual(config['endpoint_name'], '主端点')
        self.assertEqual(config['api_endpoint'], 'https://93.184.216.34')
        self.assertEqual(config['model_name'], 'gpt-4')

    def test_create_app_config_deactivates_same_app_others(self):
        """创建 is_active=True AppConfig,自动取消同 app_name 的其他 active 配置."""
        old = LlmAppConfig.objects.create(
            app_name="smart_assistant", endpoint=self.endpoint,
            model_name="gpt-3.5", is_active=True,
        )

        response = self.client.post(
            '/api/smart-assistant/app-configs/',
            {
                'app_name': 'smart_assistant',
                'endpoint': self.endpoint.id,
                'model_name': 'gpt-4',
                'is_active': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        old.refresh_from_db()
        self.assertFalse(old.is_active, "同 app_name 的旧 active 配置应自动取消")
        new = LlmAppConfig.objects.get(model_name='gpt-4')
        self.assertTrue(new.is_active)


class TestLlmConfigSecurityBoundaries(TestCase):
    """LLM 全局配置的管理权限与出站请求安全边界。"""

    def setUp(self):
        self.admin = CustomUser.objects.create_user(username="security-admin", password="admin123", is_staff=True)
        self.user = CustomUser.objects.create_user(username="普通用户", password="user123")
        self.endpoint = LlmEndpoint.objects.create(name="安全测试端点", api_endpoint="https://93.184.216.34", api_key="secret-key", is_active=True)
        self.config = LlmAppConfig.objects.create(app_name="smart_assistant", endpoint=self.endpoint, model_name="test-model", is_active=True)
        self.client = APIClient()

    def test_unauthenticated_config_endpoints_return_401(self):
        self.assertEqual(self.client.get("/api/smart-assistant/endpoints/").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get("/api/smart-assistant/app-configs/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_cannot_read_or_mutate_global_llm_config(self):
        self.client.force_authenticate(user=self.user)
        endpoint_url = f"/api/smart-assistant/endpoints/{self.endpoint.id}/"
        config_url = f"/api/smart-assistant/app-configs/{self.config.id}/"
        requests = [("get", "/api/smart-assistant/endpoints/", {}), ("get", endpoint_url, {}), ("post", "/api/smart-assistant/endpoints/", {"name": "投毒", "api_endpoint": "https://evil.test", "api_key": "x"}), ("patch", endpoint_url, {"name": "投毒"}), ("put", endpoint_url, {"name": "投毒", "api_endpoint": "https://evil.test", "api_key": "x"}), ("delete", endpoint_url, {}), ("get", "/api/smart-assistant/app-configs/", {}), ("get", config_url, {}), ("post", "/api/smart-assistant/app-configs/", {"app_name": "smart_assistant", "endpoint": self.endpoint.id, "model_name": "evil"}), ("patch", config_url, {"model_name": "evil"}), ("put", config_url, {"app_name": "smart_assistant", "endpoint": self.endpoint.id, "model_name": "evil"}), ("delete", config_url, {}), ("post", f"/api/smart-assistant/endpoints/{self.endpoint.id}/fetch-models/", {}), ("post", f"/api/smart-assistant/endpoints/{self.endpoint.id}/test-endpoint/", {})]
        for method, url, data in requests:
            response = getattr(self.client, method)(url, data, format="json") if data else getattr(self.client, method)(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, (method, url, response.data))

    @patch("smart_assistant.views.llm_config.http_requests.get")
    @patch("smart_assistant.ssrf.socket.getaddrinfo")
    def test_admin_probe_uses_safe_headers_and_disables_redirects(self, mock_getaddrinfo, mock_get):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        response = MagicMock(status_code=200)
        response.json.return_value = {"data": [{"id": "safe-model"}]}
        response.raise_for_status.return_value = None
        mock_get.return_value = response
        self.client.force_authenticate(user=self.admin)
        result = self.client.post(f"/api/smart-assistant/endpoints/{self.endpoint.id}/fetch-models/")
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        self.assertEqual(result.data, {"models": ["safe-model"], "count": 1})
        kwargs = mock_get.call_args.kwargs
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret-key")

    def test_admin_probe_rejects_ssrf_urls_without_network_access(self):
        self.client.force_authenticate(user=self.admin)
        blocked_urls = ["http://localhost/v1", "http://127.0.0.1/v1", "http://192.168.1.10/v1", "http://169.254.169.254/latest/meta-data", "http://[::1]/v1", "http://user:password@example.com/v1", "ftp://example.com/v1"]
        with patch("smart_assistant.views.llm_config.http_requests.get") as mock_get:
            for url in blocked_urls:
                self.endpoint.api_endpoint = url
                self.endpoint.save(update_fields=["api_endpoint"])
                result = self.client.post(f"/api/smart-assistant/endpoints/{self.endpoint.id}/test-endpoint/")
                self.assertEqual(result.status_code, status.HTTP_400_BAD_REQUEST, url)
                self.assertIn("端点地址", str(result.data))
            mock_get.assert_not_called()

    @patch("smart_assistant.views.llm_config.http_requests.get")
    @patch("smart_assistant.ssrf.socket.getaddrinfo")
    def test_admin_probe_does_not_follow_redirects(self, mock_getaddrinfo, mock_get):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        response = MagicMock(status_code=302, headers={"Location": "http://169.254.169.254/"})
        response.raise_for_status.return_value = None
        mock_get.return_value = response
        self.client.force_authenticate(user=self.admin)
        result = self.client.post(f"/api/smart-assistant/endpoints/{self.endpoint.id}/test-endpoint/")
        self.assertEqual(result.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertNotIn("secret-key", str(result.data))
        self.assertFalse(mock_get.call_args.kwargs["allow_redirects"])
