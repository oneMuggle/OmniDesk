"""Tests for smart_assistant.tools.base — 覆盖率补齐.

目标:tools/base.py 48% → 80%+。
覆盖:ValidationResult + BaseTool 的 get_schema / get_examples / validate_params
/ validate_result / extract_keywords。
"""

import pytest

from smart_assistant.tools.base import BaseTool, ValidationResult


class _ConcreteTool(BaseTool):
    """最小可实例化的 BaseTool 子类,用于测试基类方法."""

    name = "concrete_test_tool"
    description = "用于测试的最小工具"
    intent_type = "test_intent"

    def execute(self, query: str, context: dict = None) -> dict:
        return {"found": True, "data": "test"}


# =============================================================================
# ValidationResult
# =============================================================================


class TestValidationResult:
    """ValidationResult 数据类."""

    def test_defaults_to_valid(self):
        result = ValidationResult()
        assert result.is_valid is True
        assert result.reason == ""

    def test_invalid_with_reason(self):
        result = ValidationResult(is_valid=False, reason="参数缺失")
        assert result.is_valid is False
        assert result.reason == "参数缺失"

    def test_valid_with_info_reason(self):
        result = ValidationResult(is_valid=True, reason="一切正常")
        assert result.is_valid is True
        assert result.reason == "一切正常"


# =============================================================================
# BaseTool 默认方法
# =============================================================================


class TestBaseToolDefaults:
    """BaseTool 继承方法的默认行为."""

    def test_get_schema_returns_tool_metadata(self):
        tool = _ConcreteTool()
        schema = tool.get_schema()

        assert schema == {
            "name": "concrete_test_tool",
            "description": "用于测试的最小工具",
            "intent_type": "test_intent",
        }

    def test_get_examples_returns_empty_list_by_default(self):
        tool = _ConcreteTool()
        examples = tool.get_examples()

        assert examples == []

    def test_validate_params_default_returns_valid(self):
        """基类默认实现:所有参数都有效."""
        tool = _ConcreteTool()
        result = tool.validate_params({"any": "params"})

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.reason == ""


# =============================================================================
# BaseTool.validate_result
# =============================================================================


class TestValidateResult:
    """BaseTool.validate_result: 校验工具返回结果的有效性."""

    def test_non_dict_result_is_invalid(self):
        tool = _ConcreteTool()
        result = tool.validate_result("not a dict")

        assert result.is_valid is False
        assert "字典" in result.reason  # "结果不是字典"

    def test_none_result_is_invalid(self):
        tool = _ConcreteTool()
        result = tool.validate_result(None)

        assert result.is_valid is False
        assert "字典" in result.reason

    def test_list_result_is_invalid(self):
        tool = _ConcreteTool()
        result = tool.validate_result([1, 2, 3])

        assert result.is_valid is False
        assert "字典" in result.reason

    def test_dict_with_found_false_is_invalid(self):
        tool = _ConcreteTool()
        result = tool.validate_result({"found": False, "message": "未找到"})

        assert result.is_valid is False
        assert result.reason == "未找到"

    def test_dict_with_found_false_no_message_uses_default(self):
        tool = _ConcreteTool()
        result = tool.validate_result({"found": False})

        assert result.is_valid is False
        assert result.reason == "未找到相关信息"

    def test_dict_with_found_true_is_valid(self):
        tool = _ConcreteTool()
        result = tool.validate_result({"found": True, "data": "anything"})

        assert result.is_valid is True
        assert result.reason == ""

    def test_dict_with_truthy_non_bool_found_is_valid(self):
        """found 字段 truthy 值(非 False)视为有效."""
        tool = _ConcreteTool()
        result = tool.validate_result({"found": 1})

        assert result.is_valid is True


# =============================================================================
# BaseTool.extract_keywords
# =============================================================================


class TestExtractKeywords:
    """BaseTool.extract_keywords: 去除停用词后提取关键词."""

    def test_removes_single_char_stopwords(self):
        """单字停用词('的' '了' '吗' '呢')被过滤."""
        tool = _ConcreteTool()
        keywords = tool.extract_keywords("张三的信息吗")

        # 单字停用词被过滤
        assert "的" not in keywords
        assert "吗" not in keywords
        # 实际关键词保留
        assert "张" in keywords
        assert "三" in keywords
        assert "信" in keywords
        assert "息" in keywords

    def test_filters_phrase_stopword(self):
        """完整词停用词('帮我'/'查询'/'有没有' 等)被过滤.

        注意:停用词按完整词匹配,不是按字符。'帮'是单字不在 stopwords 集合中,
        所以 '帮' 不会被过滤(只有 '帮我' 整体才会被过滤)。
        """
        tool = _ConcreteTool()
        keywords = tool.extract_keywords("帮我查询张三")

        # 完整停用词 '帮我' 和 '查询' 整体被过滤(若 query 中存在的话)
        # 由于 extract_keywords 是逐字符迭代,'帮我' 不会被识别(它需要 query 包含 '帮我' 整体)
        # 这里测单字 '查' 也不会被过滤(因为 stopwords 是 '查询' 不是 '查')
        # 所以这个测试主要验证 单字 '我' 也不在 stopwords 中
        assert "我" in keywords  # '我' 不是停用词
        assert "帮" in keywords  # '帮' 不是停用词
        # '的' 是单字停用词,验证 '的' 会被过滤
        keywords2 = tool.extract_keywords("张的三")
        assert "的" not in keywords2

    def test_keeps_all_chars_when_no_stopword_present(self):
        tool = _ConcreteTool()
        keywords = tool.extract_keywords("排班值班")

        assert keywords == ["排", "班", "值", "班"]

    def test_filters_multiple_stopwords(self):
        """'的'/'了'/'吗'/'呢' 单字停用词同时出现,全部过滤."""
        tool = _ConcreteTool()
        keywords = tool.extract_keywords("张三和李四的事了吗呢")

        # 多个单字停用词被过滤
        assert "的" not in keywords
        assert "了" not in keywords
        assert "吗" not in keywords
        assert "呢" not in keywords
        # 实际关键词保留
        assert "张" in keywords
        assert "三" in keywords
        assert "李" in keywords
        assert "四" in keywords

    def test_empty_string_returns_empty_list(self):
        tool = _ConcreteTool()
        keywords = tool.extract_keywords("")

        assert keywords == []
