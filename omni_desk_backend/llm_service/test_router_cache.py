"""R5-B4: LLMRouter 配置加载缓存测试。

覆盖:
1. _load_configs 结果写入缓存,第二次构造不再打 DB
2. LlmAppConfig 变更后缓存失效
3. LlmEndpoint 变更后缓存失效
4. 缓存 TTL 为 60s
"""

import pytest
from django.core.cache import cache
from unittest.mock import patch

from smart_assistant.models import LlmAppConfig, LlmEndpoint

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def endpoint(db):
    return LlmEndpoint.objects.create(name="测试端点", api_endpoint="https://api.example.com", api_key="sk-test")


class TestRouterConfigCache:
    def test_load_configs_populates_cache(self, endpoint):
        from llm_service.router import LLMRouter

        LlmAppConfig.objects.create(app_name="smart_assistant", endpoint=endpoint, model_name="m1", is_active=True)
        router = LLMRouter(app_name="smart_assistant")
        assert len(router._configs) == 1
        assert cache.get("llm_router_configs_smart_assistant") is not None

    def test_second_construction_hits_cache(self, endpoint):
        """第二次构造命中缓存:改 DB 后新构造的 router 仍看到旧配置(未失效时)。"""
        from llm_service.router import LLMRouter

        config = LlmAppConfig.objects.create(
            app_name="smart_assistant", endpoint=endpoint, model_name="m1", is_active=True
        )
        first = LLMRouter(app_name="smart_assistant")
        assert len(first._configs) == 1

        # 绕过信号直接改 DB(模拟其他进程写入但缓存未过期)
        LlmAppConfig.objects.filter(pk=config.pk).update(model_name="changed")
        second = LLMRouter(app_name="smart_assistant")
        assert [c.model_name for c in second._configs] == ["m1"]

    def test_app_config_change_invalidates_cache(self, endpoint):
        from llm_service.router import LLMRouter

        LLMRouter(app_name="smart_assistant")  # 建立缓存(空配置)
        assert cache.get("llm_router_configs_smart_assistant") == []

        LlmAppConfig.objects.create(
            app_name="smart_assistant", endpoint=endpoint, model_name="new-model", is_active=True
        )
        assert cache.get("llm_router_configs_smart_assistant") is None
        router = LLMRouter(app_name="smart_assistant")
        assert [c.model_name for c in router._configs] == ["new-model"]

    def test_endpoint_change_invalidates_all_app_caches(self, endpoint):
        from llm_service.router import LLMRouter

        LlmAppConfig.objects.create(app_name="smart_assistant", endpoint=endpoint, model_name="m1", is_active=True)
        LlmAppConfig.objects.create(app_name="office_assistant", endpoint=endpoint, model_name="m2", is_active=True)
        LLMRouter(app_name="smart_assistant")
        LLMRouter(app_name="office_assistant")
        assert cache.get("llm_router_configs_smart_assistant") is not None
        assert cache.get("llm_router_configs_office_assistant") is not None

        # 端点变更影响所有 app 的配置 → 全部失效
        endpoint.name = "改名端点"
        endpoint.save()
        assert cache.get("llm_router_configs_smart_assistant") is None
        assert cache.get("llm_router_configs_office_assistant") is None

    def test_cache_timeout_is_60s(self, endpoint):
        from llm_service.router import LLMRouter

        with patch("llm_service.router.cache.set") as mock_set:
            LLMRouter(app_name="smart_assistant")
        assert mock_set.call_args.args[2] == 60
