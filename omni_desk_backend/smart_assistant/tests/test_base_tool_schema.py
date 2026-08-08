"""Tests for BaseTool OpenAI tool schema + validate_arguments (Task 2).

These tests cover:

1. ``get_openai_tool_schema`` 默认行为:子类不实现时调用即抛 ``NotImplementedError``
   (不强制 ``@abstractmethod`` —— 现有 18 个 BaseTool 子类尚未实现该方法,
   见 plan 的 risk note;Task 4 才会逐步实现)。
2. ``validate_arguments`` 默认实现:基于 ``get_openai_tool_schema()`` 的
   ``parameters`` 字段走 jsonschema JSON Schema 校验。
   - 通过路径:合法参数原样返回
   - 失败路径:缺必填字段抛 ``jsonschema.ValidationError``
   - 失败路径:多余字段在 ``additionalProperties: False`` 时抛 ``jsonschema.ValidationError``
3. 现有 18 个 BaseTool 子类仍可正常实例化(向后兼容)。
"""

import pytest
import jsonschema

from smart_assistant.tools.base import BaseTool


class _DummyTool(BaseTool):
    """用于测试 schema / validate_arguments 的最小工具"""

    intent_type = "_dummy_test"
    name = "_dummy_test"
    description = "用于测试"

    def execute(self, query, context):
        return {"found": True}

    @classmethod
    def get_openai_tool_schema(cls):
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": "dummy",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }


class _LegacyTool(BaseTool):
    """模拟现有 18 个工具:不实现 get_openai_tool_schema"""

    intent_type = "_legacy_test"
    name = "_legacy_test"
    description = "legacy"

    def execute(self, query, context):
        return {"found": True}


# ---------------------------------------------------------------------------
# 1. get_openai_tool_schema 默认行为
# ---------------------------------------------------------------------------


def test_legacy_tool_can_still_instantiate():
    """现有 18 个未实现 schema 的子类必须仍能实例化(向后兼容)。

    这是本任务最关键的不变量 —— 必须保证现有 1138+ 测试仍能通过。
    """
    tool = _LegacyTool()
    assert tool is not None
    assert tool.name == "_legacy_test"


def test_get_openai_tool_schema_unimplemented_raises():
    """未实现 get_openai_tool_schema 的子类,调用时抛 NotImplementedError。

    不强制 @abstractmethod(避免破坏 18 个旧工具的实例化),
    仅保证运行期调用语义清晰。
    """
    with pytest.raises(NotImplementedError):
        _LegacyTool.get_openai_tool_schema()


def test_get_openai_tool_schema_returns_dict_when_implemented():
    """实现后返回 OpenAI 兼容的 tool 描述 dict。"""
    schema = _DummyTool.get_openai_tool_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "_dummy_test"
    assert "parameters" in schema["function"]


# ---------------------------------------------------------------------------
# 2. validate_arguments 默认实现
# ---------------------------------------------------------------------------


def test_validate_arguments_passes():
    """合法参数 → 原样返回"""
    validated = _DummyTool.validate_arguments({"query": "hi"})
    assert validated == {"query": "hi"}


def test_validate_arguments_missing_required():
    """缺必填字段 → jsonschema.ValidationError"""
    with pytest.raises(jsonschema.ValidationError):
        _DummyTool.validate_arguments({})


def test_validate_arguments_additional_property():
    """additionalProperties=False 时,多余字段 → ValidationError"""
    with pytest.raises(jsonschema.ValidationError):
        _DummyTool.validate_arguments({"query": "hi", "extra": 1})


def test_validate_arguments_wrong_type():
    """字段类型错误 → ValidationError(例如 query 应为 string)"""
    with pytest.raises(jsonschema.ValidationError):
        _DummyTool.validate_arguments({"query": 123})
