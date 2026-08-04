"""swap_extractor 单元测试"""

from unittest.mock import patch


from smart_assistant.extractors.swap_extractor import (
    _call_llm_for_json,
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
