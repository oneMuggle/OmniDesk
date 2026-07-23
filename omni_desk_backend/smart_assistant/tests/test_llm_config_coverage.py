"""
覆盖补齐测试:views/llm_config.py(基线 37%,目标 ≥85%)

补 8 个测试用例:
  1. 端点列表按 created_at 倒序
  2. 创建端点时 is_active 互斥
  3. 更新端点时 is_active 互斥
  4. fetch-models 成功
  5. fetch-models 超时
  6. fetch-models 连接失败
  7. test-endpoint 401 单独处理
  8. app-config 同 app_name 互斥 + serializer 选择
  9. app-config 切换激活
"""

from unittest.mock import patch, MagicMock

import pytest
import requests as http_requests

from smart_assistant.models import LlmEndpoint, LlmAppConfig


# =============================================================================
# LlmEndpointViewSet
# =============================================================================


@pytest.mark.django_db
class TestLlmEndpointViewSet:
    """端点管理:CRUD + is_active 互斥 + fetch-models / test-endpoint."""

    def _make_endpoint(self, **kwargs):
        defaults = dict(
            name="默认 OpenAI",
            api_endpoint="https://api.openai.com",
            api_key="sk-test-123456",
            is_active=False,
        )
        defaults.update(kwargs)
        return LlmEndpoint.objects.create(**defaults)

    def test_endpoint_list_returns_ordered_by_created_at(self, admin_client):
        """端点列表按 created_at 倒序."""
        self._make_endpoint(name="旧端点")
        new = self._make_endpoint(name="新端点")

        resp = admin_client.get("/api/smart-assistant/endpoints/")
        assert resp.status_code == 200
        ids = [e["id"] for e in resp.json()["results"]]
        assert ids[0] == new.id  # 最新创建在前

    def test_endpoint_create_activates_deactivates_others(self, admin_client):
        """创建 is_active=True 端点时,其他端点自动取消激活."""
        old = self._make_endpoint(name="旧激活", is_active=True)

        resp = admin_client.post(
            "/api/smart-assistant/endpoints/",
            {
                "name": "新激活",
                "api_endpoint": "https://api.example.com",
                "api_key": "sk-new",
                "is_active": True,
                "priority": 1,
            },
            format="json",
        )
        assert resp.status_code == 201

        old.refresh_from_db()
        assert old.is_active is False  # 旧的被自动取消

    def test_endpoint_update_toggles_activation(self, admin_client):
        """更新端点为 is_active=True 时,其他端点自动取消."""
        a = self._make_endpoint(name="A", is_active=True)
        b = self._make_endpoint(name="B", is_active=False)

        resp = admin_client.patch(
            f"/api/smart-assistant/endpoints/{b.id}/",
            {"is_active": True},
            format="json",
        )
        assert resp.status_code == 200

        a.refresh_from_db()
        b.refresh_from_db()
        assert a.is_active is False
        assert b.is_active is True

    @patch("smart_assistant.views.llm_config.http_requests.get")
    def test_endpoint_fetch_models_success(self, mock_get, admin_client):
        """fetch-models 成功返回模型列表."""
        endpoint = self._make_endpoint()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"id": "gpt-4"},
                {"id": "gpt-3.5-turbo"},
                {"name": "no_id_key"},  # 无 id 字段,应被过滤
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        resp = admin_client.post(f"/api/smart-assistant/endpoints/{endpoint.id}/fetch-models/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert body["models"] == ["gpt-3.5-turbo", "gpt-4"]  # 排序

    @patch("smart_assistant.views.llm_config.http_requests.get")
    def test_endpoint_fetch_models_timeout(self, mock_get, admin_client):
        """fetch-models 超时返回 504."""
        endpoint = self._make_endpoint()
        mock_get.side_effect = http_requests.exceptions.Timeout("timed out")

        resp = admin_client.post(f"/api/smart-assistant/endpoints/{endpoint.id}/fetch-models/")
        assert resp.status_code == 504
        assert "超时" in resp.json()["error"]

    @patch("smart_assistant.views.llm_config.http_requests.get")
    def test_endpoint_fetch_models_connection_error(self, mock_get, admin_client):
        """fetch-models 连接失败返回 502."""
        endpoint = self._make_endpoint()
        mock_get.side_effect = http_requests.exceptions.ConnectionError("refused")

        resp = admin_client.post(f"/api/smart-assistant/endpoints/{endpoint.id}/fetch-models/")
        assert resp.status_code == 502
        assert "无法连接" in resp.json()["error"]

    @patch("smart_assistant.views.llm_config.http_requests.get")
    def test_endpoint_test_endpoint_unauthorized(self, mock_get, admin_client):
        """test-endpoint 在 401 时单独处理,返回 401 + auth_error."""
        endpoint = self._make_endpoint()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "invalid api key"
        # raise_for_status 会抛 HTTPError,response 属性是 mock_resp
        http_error = http_requests.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_resp

        resp = admin_client.post(f"/api/smart-assistant/endpoints/{endpoint.id}/test-endpoint/")
        assert resp.status_code == 401
        body = resp.json()
        assert body["status"] == "auth_error"
        assert "认证失败" in body["message"]


# =============================================================================
# LlmAppConfigViewSet
# =============================================================================


@pytest.mark.django_db
class TestLlmAppConfigViewSet:
    """应用配置:CRUD + 同 app_name is_active 互斥."""

    def _setup(self):
        endpoint1 = LlmEndpoint.objects.create(
            name="E1", api_endpoint="https://a.com", api_key="k1", is_active=True
        )
        endpoint2 = LlmEndpoint.objects.create(
            name="E2", api_endpoint="https://b.com", api_key="k2", is_active=False
        )
        return endpoint1, endpoint2

    def test_appconfig_create_deactivates_same_app_only(self, admin_client):
        """创建同 app_name 的 is_active=True 配置时,只禁用同 app 的其他 config."""
        endpoint1, endpoint2 = self._setup()
        cfg_old = LlmAppConfig.objects.create(
            app_name="smart_assistant",
            endpoint=endpoint1,
            model_name="gpt-4",
            is_active=True,
        )

        resp = admin_client.post(
            "/api/smart-assistant/app-configs/",
            {
                "app_name": "smart_assistant",
                "endpoint": endpoint2.id,
                "model_name": "gpt-3.5",
                "is_active": True,
            },
            format="json",
        )
        assert resp.status_code == 201

        cfg_old.refresh_from_db()
        assert cfg_old.is_active is False  # 同 app_name 旧 config 被禁用

    def test_appconfig_serializer_selection_by_action(self, admin_client):
        """get_serializer_class 根据 action 选择 Create/普通 Serializer."""
        endpoint, _ = self._setup()

        LlmAppConfig.objects.create(
            app_name="smart_assistant",
            endpoint=endpoint,
            model_name="gpt-4",
        )

        resp = admin_client.get("/api/smart-assistant/app-configs/")
        assert resp.status_code == 200
        first = resp.json()["results"][0]
        assert "endpoint_name" in first
        assert first["endpoint_name"] == "E1"
        assert first["api_endpoint"] == "https://a.com"

    def test_appconfig_update_keeps_only_one_active(self, admin_client):
        """更新一个 config 为 is_active=True,其他同 app_name 的变为 False."""
        endpoint1, endpoint2 = self._setup()
        cfg_a = LlmAppConfig.objects.create(
            app_name="smart_assistant",
            endpoint=endpoint1,
            model_name="gpt-4",
            is_active=True,
        )
        cfg_b = LlmAppConfig.objects.create(
            app_name="smart_assistant",
            endpoint=endpoint2,
            model_name="gpt-3.5",
            is_active=False,
        )

        # 切换激活到 cfg_b
        resp = admin_client.patch(
            f"/api/smart-assistant/app-configs/{cfg_b.id}/",
            {"is_active": True},
            format="json",
        )
        assert resp.status_code == 200

        cfg_a.refresh_from_db()
        cfg_b.refresh_from_db()
        assert cfg_a.is_active is False
        assert cfg_b.is_active is True
