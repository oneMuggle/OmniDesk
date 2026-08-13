"""MemoUpdateTool LLM extractor 单测(patch _call_update_llm)。"""
from unittest.mock import patch

from django.test import TestCase

from smart_assistant.extractors.memo_update_extractor import (
    UpdateParams,
    extract_update_params,
)


class TestExtractUpdateParams(TestCase):
    def test_parses_full_update(self):
        with patch(
            "smart_assistant.extractors.memo_update_extractor._call_update_llm"
        ) as mock_llm:
            mock_llm.return_value = (
                '{"target_title": "开会", "new_title": "周会", '
                '"new_content": "季度总结", "new_reminder_time": "2026-08-14T15:00:00"}'
            )
            params = extract_update_params("把开会的备忘改成周会")
        self.assertIsInstance(params, UpdateParams)
        self.assertEqual(params.target_title, "开会")
        self.assertEqual(params.new_title, "周会")
        self.assertEqual(params.new_content, "季度总结")
        self.assertEqual(params.new_reminder_time, "2026-08-14T15:00:00")

    def test_returns_none_when_target_missing(self):
        with patch(
            "smart_assistant.extractors.memo_update_extractor._call_update_llm"
        ) as mock_llm:
            mock_llm.return_value = '{"new_title": "周会"}'
            params = extract_update_params("改标题")
        self.assertIsNone(params)

    def test_returns_none_when_no_changes(self):
        with patch(
            "smart_assistant.extractors.memo_update_extractor._call_update_llm"
        ) as mock_llm:
            mock_llm.return_value = '{"target_title": "开会"}'
            params = extract_update_params("把开会那天的备忘改一下")
        self.assertIsNone(params)

    def test_returns_none_when_llm_fails(self):
        with patch(
            "smart_assistant.extractors.memo_update_extractor._call_update_llm"
        ) as mock_llm:
            mock_llm.return_value = None
            params = extract_update_params("改备忘")
        self.assertIsNone(params)
