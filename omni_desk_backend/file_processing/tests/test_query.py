"""P1A-1:Migration from ollama.Client to LLMRouter.generate。

旧 ``test_query.py`` 的 3 个测试已重写:
- ``test_query_basic`` / ``test_query_empty_data``: mock 目标从
  ``file_processing.ai.query.Client`` 改为 ``llm_service.router.LLMRouter.generate``
- ``test_build_prompt``: 直接验证 ``_build_prompt`` 输出,无需 LLM mock
"""
from unittest.mock import patch

from file_processing.ai.query import NaturalLanguageQuery


class TestNaturalLanguageQuery:

    @patch("llm_service.router.LLMRouter.generate")
    def test_query_basic(self, mock_generate):
        mock_generate.return_value = (
            "2月份的销售额最高，为15000元。",
            {
                "total_tokens": 30,
                "model_name": "qwen2.5:7b",
                "estimated_cost": 0.0,
                "endpoint_id": None,
            },
        )
        query = NaturalLanguageQuery()
        context = {
            "sheets_data": [
                {
                    "name": "销售数据",
                    "headers": ["月份", "销售额"],
                    "data": [
                        ["1月", 10000],
                        ["2月", 15000],
                        ["3月", 12000],
                    ],
                }
            ]
        }

        answer, usage = query.query("哪个月份销售额最高？", context)

        assert "2月" in answer or "15000" in answer
        assert usage["total_tokens"] == 30
        assert usage["model_name"] == "qwen2.5:7b"
        mock_generate.assert_called_once()

    @patch("llm_service.router.LLMRouter.generate")
    def test_query_empty_data(self, mock_generate):
        """空数据短路:LLMRouter.generate 不应被调用,early-return 元数据完整。"""
        query = NaturalLanguageQuery()
        context = {"sheets_data": []}

        content, usage = query.query("数据是什么？", context)

        assert "没有表格数据" in content
        assert usage["model_name"] == "qwen2.5:7b"
        assert usage["estimated_cost"] == 0.0
        assert usage["endpoint_id"] is None
        # 短路早期返回,LLM 调用零次(节省 token)
        mock_generate.assert_not_called()

    def test_build_prompt(self):
        query = NaturalLanguageQuery()
        context = {
            "sheets_data": [
                {
                    "name": "Sales",
                    "headers": ["Product", "Price"],
                    "data": [
                        ["Apple", 10],
                        ["Banana", 5],
                    ],
                }
            ]
        }

        prompt = query._build_prompt("What is the total?", context)

        # 校验 markdown 表格结构(列名 + 数据均出现)
        assert "Sales" in prompt
        assert "Product" in prompt
        assert "Price" in prompt
        assert "Apple" in prompt
        assert "What is the total?" in prompt