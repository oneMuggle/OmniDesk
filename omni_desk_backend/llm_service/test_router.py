"""LLMRouter 测试：Ollama 兜底模型读 settings + app_name 配置隔离。

覆盖:
- Ollama 兜底模型优先取 settings.OLLAMA_MODEL_NAME（不再硬编码）
- settings 无该配置/为空时回退类常量 OLLAMA_MODEL
- 不同 app_name 各自加载专属 LlmAppConfig，无专属配置时兜底链仍可用
- get_router 按 app_name 缓存独立单例
"""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

import llm_service.router as router_module
from llm_service.router import LLMRouter, get_router


def _fake_response(content="回答", usage=None):
    """构造 requests.post 的 mock 响应（OpenAI 兼容格式）。"""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": usage,
    }
    return resp


@pytest.mark.django_db
class TestOllamaFallbackModel:
    """Ollama 兜底模型必须跟随 settings，不允许硬编码。"""

    def test_fallback_model_reads_settings(self):
        """兜底命中 Ollama 时，模型名取自 settings.OLLAMA_MODEL_NAME。"""
        with override_settings(OLLAMA_MODEL_NAME="custom-model:7b"):
            with patch("llm_service.router.requests.post") as mock_post:
                mock_post.return_value = _fake_response(usage={"total_tokens": 10})
                content, usage = LLMRouter().generate(prompt="你好")

        assert content == "回答"
        # usage 与实际请求体中的模型名都应是 settings 指定值
        assert usage["model_name"] == "custom-model:7b"
        sent_payload = mock_post.call_args.kwargs["json"]
        assert sent_payload["model"] == "custom-model:7b"

    def test_generate_with_tools_uses_internal_transport_for_ollama_fallback(self):
        router = LLMRouter()
        with patch("llm_service.router.safe_request", side_effect=AssertionError("DB transport used")):
            with patch("llm_service.router.safe_internal_request") as internal:
                internal.return_value = _fake_response(content="工具兜底", usage={"total_tokens": 1})
                content, _usage, _calls = router.generate_with_tools(
                    messages=[{"role": "user", "content": "你好"}],
                )
        assert content == "工具兜底"
        assert internal.call_args.args[:2] == ("POST", "http://localhost:11434/v1/chat/completions")

    def test_fallback_model_falls_back_to_class_constant(self):
        """settings 未提供有效值时回退类常量（统一默认 qwen2.5:7b）。"""
        assert LLMRouter.OLLAMA_MODEL == "qwen2.5:7b"
        with override_settings(OLLAMA_MODEL_NAME=None):
            assert LLMRouter._resolve_ollama_model() == "qwen2.5:7b"

    def test_fallback_model_default_settings_value(self):
        """未 override 时 settings 默认值与类常量一致（全站统一）。"""
        from django.conf import settings

        assert settings.OLLAMA_MODEL_NAME == LLMRouter.OLLAMA_MODEL


@pytest.mark.django_db
class TestAppNameIsolation:
    """各应用通过 app_name 隔离 DB 端点配置。"""

    def _create_endpoint_and_config(self, app_name, model_name):
        from smart_assistant.models import LlmAppConfig, LlmEndpoint

        endpoint = LlmEndpoint.objects.create(
            name=f"端点-{app_name}",
            api_endpoint="https://api.example.com",
            api_key="sk-test",
        )
        LlmAppConfig.objects.create(
            app_name=app_name,
            endpoint=endpoint,
            model_name=model_name,
            is_active=True,
        )
        return endpoint

    def test_router_loads_only_own_app_configs(self):
        """路由只加载自己 app_name 的配置；office_assistant 无专属配置时为空。"""
        self._create_endpoint_and_config("smart_assistant", "smart-model")

        smart_router = LLMRouter(app_name="smart_assistant")
        office_router = LLMRouter(app_name="office_assistant")

        assert len(smart_router._configs) == 1
        assert smart_router._configs[0].model_name == "smart-model"
        # 无专属配置：交由全局 Ollama 兜底链处理
        assert office_router._configs == []

    def test_office_app_without_config_uses_ollama_fallback(self):
        """无专属配置的应用调用 generate 时应命中 Ollama 兜底端点。"""
        office_router = LLMRouter(app_name="office_assistant")
        with patch("llm_service.router.requests.post") as mock_post:
            mock_post.return_value = _fake_response(content="兜底回答", usage={"total_tokens": 5})
            content, usage = office_router.generate(prompt="你好")

        assert content == "兜底回答"
        # Ollama 兜底：无端点 ID、成本为 0
        assert usage["endpoint_id"] is None
        assert usage["estimated_cost"] == 0.0
        # 请求打向本地 Ollama 的 OpenAI 兼容端点
        called_url = mock_post.call_args.args[0]
        assert called_url == "http://localhost:11434/v1/chat/completions"




class TestRequestTimeoutResolution:
    """请求超时配置不得通过实例化或 monkeypatch 污染全局状态。"""

    def test_base_default_uses_settings(self, settings):
        settings.LLM_REQUEST_TIMEOUT_SECONDS = 37
        assert LLMRouter().REQUEST_TIMEOUT == 37

    def test_explicit_base_class_timeout_wins_over_settings(self, settings):
        settings.LLM_REQUEST_TIMEOUT_SECONDS = 37
        with patch.object(LLMRouter, "REQUEST_TIMEOUT", 120):
            assert LLMRouter().REQUEST_TIMEOUT == 120

    def test_subclass_override_wins_over_settings(self, settings):
        settings.LLM_REQUEST_TIMEOUT_SECONDS = 37

        class CustomRouter(LLMRouter):
            REQUEST_TIMEOUT = 88

        assert CustomRouter().REQUEST_TIMEOUT == 88

    def test_monkeypatch_restore_does_not_pollute_following_instances(self, settings):
        settings.LLM_REQUEST_TIMEOUT_SECONDS = 41
        with patch.object(LLMRouter, "REQUEST_TIMEOUT", 9):
            assert LLMRouter().REQUEST_TIMEOUT == 9
        assert LLMRouter().REQUEST_TIMEOUT == 41


class TestGetRouterSingleton:
    """get_router 按 app_name 缓存独立单例。"""

    def setup_method(self, method):
        # 隔离模块级缓存，避免测试间互相污染
        self._saved = dict(router_module._routers)

    def teardown_method(self, method):
        router_module._routers.clear()
        router_module._routers.update(self._saved)

    def test_same_app_returns_same_instance(self):
        router_a = get_router(app_name="office_assistant")
        router_b = get_router(app_name="office_assistant")
        assert router_a is router_b
        assert router_a.app_name == "office_assistant"

    def test_different_apps_return_distinct_instances(self):
        smart = get_router()  # 默认 smart_assistant，兼容既有调用方
        office = get_router(app_name="office_assistant")
        assert smart is not office
        assert smart.app_name == "smart_assistant"
        assert office.app_name == "office_assistant"
