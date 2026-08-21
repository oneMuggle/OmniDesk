"""Tests for smart_assistant.tools.base — 覆盖率补齐.

目标:tools/base.py 48% → 80%+。
覆盖:ValidationResult + BaseTool 的 get_schema / get_examples / validate_params
/ validate_result / extract_keywords。
"""

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

        # risk_level: 工具权限分级新增字段,BaseTool 默认 "read"
        assert schema == {
            "name": "concrete_test_tool",
            "description": "用于测试的最小工具",
            "intent_type": "test_intent",
            "risk_level": "read",
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
# BaseTool.extract_keywords(R5-D2 统一后:str -> str replace 链语义)
# =============================================================================


class TestExtractKeywords:
    """BaseTool.extract_keywords: 剥离指令词与 stopwords 后返回字符串.

    R5-D2 重构后默认指令词为 搜索/查找;裸子类无领域 stopwords。
    更细粒度的等价性断言见 test_extract_keywords_unified.py。
    """

    def test_returns_str(self):
        """返回类型是 str(重构前为 list)."""
        tool = _ConcreteTool()
        keywords = tool.extract_keywords("张三的信息")

        assert isinstance(keywords, str)

    def test_strips_default_command_words(self):
        """默认指令词 搜索/查找 被剥离."""
        tool = _ConcreteTool()

        assert tool.extract_keywords("搜索张三") == "张三"
        assert tool.extract_keywords("查找张三") == "张三"

    def test_keeps_non_command_chars(self):
        """非指令词内容原样保留."""
        tool = _ConcreteTool()

        assert tool.extract_keywords("排班值班") == "排班值班"

    def test_no_whitespace_only_strip_ends(self):
        """仅首尾空白被 strip,中间空白保留."""
        tool = _ConcreteTool()

        assert tool.extract_keywords("  张三 李四  ") == "张三 李四"

    def test_empty_string_returns_empty_string(self):
        tool = _ConcreteTool()
        keywords = tool.extract_keywords("")

        assert keywords == ""
