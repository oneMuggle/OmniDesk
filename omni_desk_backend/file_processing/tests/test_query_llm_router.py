"""NaturalLanguageQuery 改走 LLMRouter 而非 ollama.Client。"""
from unittest.mock import patch

from file_processing.ai.query import NaturalLanguageQuery


class TestNaturalLanguageQueryViaLLMRouter:
    """P1A-1:query() 走 LLMRouter.generate(),不再 import ollama.Client。"""

    def test_query_calls_llm_router_not_ollama_client(self):
        """query() 走 LLMRouter.generate,返回 (content, usage) 元组。"""
        with patch("llm_service.router.LLMRouter.generate") as mock_generate:
            mock_generate.return_value = (
                "2月最高",
                {
                    "total_tokens": 42,
                    "model_name": "qwen2.5:7b",
                    "estimated_cost": 0.0,
                    "endpoint_id": None,
                },
            )

            q = NaturalLanguageQuery()
            sheets_data = [
                {
                    "name": "x",
                    "headers": ["月"],
                    "data": [["1月"], ["2月"], ["3月"]],
                }
            ]
            result, usage = q.query("哪月最高?", {"sheets_data": sheets_data})

            assert result == "2月最高"
            assert usage["total_tokens"] == 42
            assert usage["model_name"] == "qwen2.5:7b"
            assert usage["estimated_cost"] == 0.0
            mock_generate.assert_called_once()

    def test_query_does_not_import_ollama_sdk(self):
        """不再依赖 ollama Python SDK(LLMRouter 走 OpenAI 兼容 HTTP)。"""
        import file_processing.ai.query as q_module
        # 间接验证:模块不应持有 ollama Client 属性
        assert not hasattr(q_module, "Client")