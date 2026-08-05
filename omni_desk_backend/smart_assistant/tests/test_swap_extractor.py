"""swap_extractor 单元测试"""

from unittest.mock import MagicMock, patch

import pytest

from smart_assistant.extractors.swap_extractor import (
    CreateParams,
    DecideParams,
    _call_llm_for_json,
    extract_create_params,
    extract_decide_params,
)


class TestCallLlmForJson:
    """_call_llm_for_json:LLM 返回值 → 解析为 dict,失败 → None"""

    def test_valid_json(self):
        """纯 JSON 字符串直接解析"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"target_name": "李四", "duty_date": "2026-08-12"}',
        ):
            result = _call_llm_for_json("fake prompt")
        assert result == {"target_name": "李四", "duty_date": "2026-08-12"}

    def test_json_embedded_in_text(self):
        """LLM 在文本中嵌入 JSON,正则提取首个 {}"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='好的,以下是结果: {"target_name": "李四"} 完毕',
        ):
            result = _call_llm_for_json("fake prompt")
        assert result == {"target_name": "李四"}

    def test_empty_string(self):
        """LLM 返回空字符串 → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value="",
        ):
            result = _call_llm_for_json("fake prompt")
        assert result is None

    def test_invalid_json(self):
        """LLM 返回非 JSON 文本 → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value="抱歉,我无法理解",
        ):
            result = _call_llm_for_json("fake prompt")
        assert result is None

    def test_json_with_markdown_fence(self):
        """LLM 用 ```json 围栏 → 正则提取"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='```json\n{"target_name": "李四"}\n```',
        ):
            result = _call_llm_for_json("fake prompt")
        assert result == {"target_name": "李四"}


@pytest.mark.django_db
class TestExtractCreateParams:
    """extract_create_params:LLM 解析 create 参数"""

    def test_valid_extraction(self):
        """LLM 返回有效 JSON → 构造 CreateParams"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"target_name": "李四", "duty_date": "2026-08-12", "reason": "出差"}',
        ):
            mock_requester = MagicMock()
            mock_requester.name = "张三"
            result = extract_create_params(
                "我想和李四换 8月12日 的班,因出差", mock_requester
            )
        assert isinstance(result, CreateParams)
        assert result.target_name == "李四"
        assert result.duty_date == "2026-08-12"
        assert result.reason == "出差"

    def test_missing_required_field(self):
        """LLM 缺 target_name → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"duty_date": "2026-08-12"}',
        ):
            mock_requester = MagicMock()
            mock_requester.name = "张三"
            result = extract_create_params("模糊 query", mock_requester)
        assert result is None

    def test_llm_failure(self):
        """LLM 抛异常 → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            side_effect=RuntimeError("LLM timeout"),
        ):
            mock_requester = MagicMock()
            mock_requester.name = "张三"
            result = extract_create_params("query", mock_requester)
        assert result is None

    def test_empty_reason_allowed(self):
        """reason 字段为空字符串是合法的"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"target_name": "李四", "duty_date": "2026-08-12", "reason": ""}',
        ):
            mock_requester = MagicMock()
            mock_requester.name = "张三"
            result = extract_create_params(
                "我想和李四换 8月12日 的班", mock_requester
            )
        assert result is not None
        assert result.reason == ""


class TestExtractDecideParams:
    """extract_decide_params:LLM 解析 decide 参数"""

    def test_accept_with_swap_id(self):
        """accept + swap_id 显式提供"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"action": "accept", "swap_id": 7, "note": "可以"}',
        ):
            mock_actor = MagicMock()
            mock_actor.personnel.name = "李四"
            result = extract_decide_params("同意申请 #7", mock_actor)
        assert isinstance(result, DecideParams)
        assert result.action == "accept"
        assert result.swap_id == 7
        assert result.note == "可以"

    def test_reject_without_swap_id(self):
        """reject 不带 swap_id → 仍合法(swap_id 兜底逻辑)"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"action": "reject", "swap_id": null, "note": ""}',
        ):
            mock_actor = MagicMock()
            mock_actor.personnel.name = "李四"
            result = extract_decide_params("拒绝张三的申请", mock_actor)
        assert result is not None
        assert result.action == "reject"
        assert result.swap_id is None

    def test_missing_action(self):
        """缺 action → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"swap_id": 7}',
        ):
            mock_actor = MagicMock()
            mock_actor.personnel.name = "李四"
            result = extract_decide_params("query", mock_actor)
        assert result is None

    def test_invalid_action(self):
        """action 不在合法集合 → None"""
        with patch(
            "smart_assistant.extractors.swap_extractor._call_llm",
            return_value='{"action": "delete", "swap_id": 7}',
        ):
            mock_actor = MagicMock()
            mock_actor.personnel.name = "李四"
            result = extract_decide_params("query", mock_actor)
        assert result is None
