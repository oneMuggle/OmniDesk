"""external_integration serializer 白名单化测试 (R3-B1)。

契约（R3-B1 PR-1）：
- IntegrationServiceSerializer：api_key 加密存储，读响应**不得**返回明文密钥（write_only）；
  写入路径仍接受 api_key。
- ExternalLinkSerializer / PluginSerializer：显式白名单字段，不随 `__all__` 暴露模型全部字段。
"""

import pytest

from external_integration.models import ExternalLink, IntegrationService, Plugin
from external_integration.serializers import (
    ExternalLinkSerializer,
    IntegrationServiceSerializer,
    PluginSerializer,
)


@pytest.mark.django_db
class TestIntegrationServiceSerializerWhitelist:
    def test_read_response_does_not_expose_api_key(self):
        """api_key 加密存储，读响应不得返回明文密钥。"""
        svc = IntegrationService.objects.create(
            name="Dify",
            slug="dify",
            integration_type="api",
            endpoint_url="http://example.com/api/v1",
            api_key="super-secret-key",
        )

        data = IntegrationServiceSerializer(svc).data

        assert "api_key" not in data

    def test_write_accepts_api_key(self):
        """写入路径仍接受 api_key（管理端可设置/更新密钥）。"""
        serializer = IntegrationServiceSerializer(
            data={
                "name": "Dify 2",
                "slug": "dify-2",
                "integration_type": "api",
                "endpoint_url": "http://example.com/api/v2",
                "api_key": "new-secret",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["api_key"] == "new-secret"

    def test_fields_whitelisted(self):
        """读响应字段 = 白名单（api_key write_only 不应出现）。"""
        svc = IntegrationService.objects.create(
            name="Dify",
            slug="dify",
            integration_type="api",
            endpoint_url="http://example.com/api/v1",
        )

        data = IntegrationServiceSerializer(svc).data

        assert set(data.keys()) == {
            "id",
            "name",
            "slug",
            "description",
            "integration_type",
            "endpoint_url",
            "embed_path",
            "config_schema",
            "metadata",
            "is_active",
            "created_at",
            "updated_at",
        }


@pytest.mark.django_db
class TestExternalLinkSerializerWhitelist:
    def test_fields_whitelisted(self):
        link = ExternalLink.objects.create(
            name="Wiki",
            url="http://example.com/wiki",
            category="docs",
        )

        data = ExternalLinkSerializer(link).data

        assert set(data.keys()) == {
            "id",
            "name",
            "url",
            "icon",
            "description",
            "category",
            "sso_enabled",
            "sso_token_endpoint",
            "sort_order",
            "is_active",
            "created_at",
            "updated_at",
        }


@pytest.mark.django_db
class TestPluginSerializerWhitelist:
    def test_fields_whitelisted(self):
        plugin = Plugin.objects.create(
            name="Test Plugin",
            slug="test-plugin",
            category="test",
            status="draft",
        )

        data = PluginSerializer(plugin).data

        assert set(data.keys()) == {
            "id",
            "name",
            "slug",
            "description",
            "author",
            "category",
            "icon",
            "status",
            "interface_version",
            "created_at",
            "updated_at",
            "versions",
        }
