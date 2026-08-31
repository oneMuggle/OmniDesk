"""任务 2(P1):LLM 成本核算。

覆盖:
- router.generate 命中 DB 端点时,usage 携带 endpoint_id / estimated_cost / model_name
- 端点无 cost_per_1k_tokens 配置时 estimated_cost 为 0,不报错
- usage 缺 total_tokens 时按 prompt_tokens + completion_tokens 计算
- API 未返回 usage 时不报错(成本字段仍存在)
- Ollama 兜底时 endpoint_id 为 None,成本为 0
- view 层把 usage 中的 estimated_cost 写入 AgentLog
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from llm_service.router import LLMRouter
from smart_assistant.models import AgentLog, LlmAppConfig, LlmEndpoint


def _fake_response(content="回答", usage=None):
    """构造 requests.post 的 mock 响应(OpenAI 兼容格式)。"""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": usage,
    }
    return resp


@pytest.mark.django_db
class TestRouterCostEnrichment:
    """LLMRouter.generate 的 usage 成本字段补充。"""

    def _create_config(self, cost):
        endpoint = LlmEndpoint.objects.create(
            name="测试端点",
            api_endpoint="https://api.example.com",
            api_key="sk-test",
            cost_per_1k_tokens=cost,
        )
        LlmAppConfig.objects.create(
            app_name="smart_assistant",
            endpoint=endpoint,
            model_name="test-model",
            is_active=True,
        )
        return endpoint

    def test_usage_carries_cost_when_configured(self):
        """有单价配置时按 token 用量计费:1000 tokens * 0.02 元/千token = 0.02 元。"""
        endpoint = self._create_config(cost=Decimal("0.02"))

        with patch("llm_service.router.safe_request") as mock_post:
            mock_post.return_value = _fake_response(
                usage={"prompt_tokens": 800, "completion_tokens": 200, "total_tokens": 1000},
            )
            content, usage = LLMRouter().generate(prompt="你好")

        assert content == "回答"
        assert usage["endpoint_id"] == endpoint.id
        assert usage["estimated_cost"] == pytest.approx(0.02)
        assert usage["model_name"] == "test-model"
        # 原有 token 字段不受影响
        assert usage["total_tokens"] == 1000

    def test_cost_zero_without_price_config(self):
        """端点未配置单价时 estimated_cost 为 0,不报错。"""
        endpoint = self._create_config(cost=None)

        with patch("llm_service.router.safe_request") as mock_post:
            mock_post.return_value = _fake_response(usage={"total_tokens": 500})
            _, usage = LLMRouter().generate(prompt="你好")

        assert usage["endpoint_id"] == endpoint.id
        assert usage["estimated_cost"] == 0.0

    def test_total_tokens_missing_uses_prompt_plus_completion(self):
        """usage 无 total_tokens 时按 prompt + completion 之和计费。"""
        self._create_config(cost=Decimal("0.01"))

        with patch("llm_service.router.safe_request") as mock_post:
            mock_post.return_value = _fake_response(
                usage={"prompt_tokens": 400, "completion_tokens": 600},
            )
            _, usage = LLMRouter().generate(prompt="你好")

        # (400 + 600) * 0.01 / 1000 = 0.01
        assert usage["estimated_cost"] == pytest.approx(0.01)

    def test_api_usage_none_does_not_crash(self):
        """API 未返回 usage 时不报错,成本字段仍存在。"""
        endpoint = self._create_config(cost=Decimal("0.02"))

        with patch("llm_service.router.safe_request") as mock_post:
            mock_post.return_value = _fake_response(usage=None)
            _, usage = LLMRouter().generate(prompt="你好")

        assert isinstance(usage, dict)
        assert usage["estimated_cost"] == 0.0
        assert usage["endpoint_id"] == endpoint.id

    def test_ollama_fallback_zero_cost(self):
        """无 DB 配置命中 Ollama 兜底时 endpoint_id 为 None,成本为 0。"""
        with patch("llm_service.router.requests.post") as mock_post:
            mock_post.return_value = _fake_response(usage={"total_tokens": 300})
            content, usage = LLMRouter().generate(prompt="你好")

        assert content == "回答"
        assert usage["endpoint_id"] is None
        assert usage["estimated_cost"] == 0.0
        assert usage["model_name"] == LLMRouter.OLLAMA_MODEL


@pytest.mark.django_db
class TestAgentLogCostWrite:
    """view 层把 estimated_cost 写入 AgentLog。"""

    @patch("smart_assistant.views.chat_sync.AgentOrchestrator")
    def test_estimated_cost_written_to_agent_log(self, mock_cls, admin_client):
        """usage 携带 estimated_cost 时写入 AgentLog.estimated_cost。"""
        mock_cls.return_value.process.return_value = {
            "answer": "正常回答",
            "intent": "general_chat",
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "error": False,
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "estimated_cost": 0.123456,
            },
        }

        resp = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "费用测试"},
            format="json",
        )

        assert resp.status_code == 200
        log = AgentLog.objects.get(user_query="费用测试")
        assert float(log.estimated_cost) == pytest.approx(0.123456)
        assert log.total_tokens == 150

    @patch("smart_assistant.views.chat_sync.AgentOrchestrator")
    def test_estimated_cost_none_when_no_usage(self, mock_cls, admin_client):
        """无 usage(如缓存命中)时 estimated_cost 为空,不报错。"""
        mock_cls.return_value.process.return_value = {
            "answer": "缓存回答",
            "intent": "general_chat",
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "error": False,
            "usage": None,
        }

        resp = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "无用量"},
            format="json",
        )

        assert resp.status_code == 200
        log = AgentLog.objects.get(user_query="无用量")
        assert log.estimated_cost is None
