"""MemoDeleteTool LLM extractor 单测(patch _call_delete_llm)。"""

from unittest.mock import patch

from django.test import TestCase

from smart_assistant.extractors.memo_delete_extractor import (
    DeleteParams,
    extract_delete_params,
)


class TestExtractDeleteParams(TestCase):
    def test_parses_target(self):
        with patch(
            "smart_assistant.extractors.memo_delete_extractor._call_delete_llm"
        ) as mock_llm:
            mock_llm.return_value = '{"target_title": "开会"}'
            params = extract_delete_params("删掉开会的备忘")
        self.assertIsInstance(params, DeleteParams)
        self.assertEqual(params.target_title, "开会")

    def test_returns_none_when_target_missing(self):
        with patch(
            "smart_assistant.extractors.memo_delete_extractor._call_delete_llm"
        ) as mock_llm:
            mock_llm.return_value = '{"confirm": true}'
            params = extract_delete_params("删掉一个备忘")
        self.assertIsNone(params)

    def test_returns_none_when_target_non_string(self):
        with patch(
            "smart_assistant.extractors.memo_delete_extractor._call_delete_llm"
        ) as mock_llm:
            mock_llm.return_value = '{"target_title": 123}'
            params = extract_delete_params("删掉一个备忘")
        self.assertIsNone(params)

    def test_returns_none_when_llm_fails(self):
        with patch(
            "smart_assistant.extractors.memo_delete_extractor._call_delete_llm"
        ) as mock_llm:
            mock_llm.return_value = None
            params = extract_delete_params("删备忘")
        self.assertIsNone(params)
