"""Memo 抽取器单元测试(LLM 全部 patch,无外部依赖)。
"""
from unittest.mock import patch
from django.test import SimpleTestCase

from smart_assistant.extractors.memo_extractor import (
    CreateParams,
    extract_create_params,
)


class TestExtractCreateParamsLLM(SimpleTestCase):
    """LLM 路径测试 - mock get_router.generate。"""

    @patch("smart_assistant.extractors.memo_extractor._call_llm")
    def test_returns_create_params_on_valid_json(self, mock_call):
        mock_call.return_value = (
            '{"title": "开会", "content": "季度总结", "reminder_time": null}'
        )
        result = extract_create_params("记一个开会")
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "开会")
        self.assertEqual(result.content, "季度总结")
        self.assertIsNone(result.reminder_time)

    @patch("smart_assistant.extractors.memo_extractor._call_llm")
    def test_returns_none_on_llm_unavailable(self, mock_call):
        mock_call.return_value = None  # _call_llm 失败兜底
        result = extract_create_params("记一个开会")
        self.assertIsNone(result)

    @patch("smart_assistant.extractors.memo_extractor._call_llm")
    def test_returns_none_on_non_json(self, mock_call):
        mock_call.return_value = "抱歉,我无法识别"  # 非 JSON
        result = extract_create_params("记一个开会")
        self.assertIsNone(result)