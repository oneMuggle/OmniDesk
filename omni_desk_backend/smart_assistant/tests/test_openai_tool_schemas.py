"""Tests for BaseTool OpenAI tool schema — 19 tools × strict JSON Schema validation.

Task 4 验证:每个 BaseTool 子类都正确实现了 get_openai_tool_schema(),
且 schema 满足 OpenAI strict 模式要求(每层 object/array 都有
additionalProperties=false)。

参数化覆盖:
- 19 个注册工具 × 2 个断言 = 38 个用例
  - test_tool_schema_is_valid_openai_function: schema 基本结构
  - test_tool_schema_is_strict: strict 模式约束(嵌套 object/array)
"""

import pytest

from smart_assistant.tools.registry import ToolRegistry


def _collect_all_tools():
    """从 ToolRegistry 实例化所有工具子类。

    注意:ToolRegistry._tools 在 apps.ready() 阶段填充,
    本测试文件被加载时 Django 已就绪(Django 测试 setup)。
    """
    return list(ToolRegistry._tools.values())


ALL_TOOL_CLASSES = _collect_all_tools()


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES, ids=lambda c: c.intent_type)
def test_tool_schema_is_valid_openai_function(tool_cls):
    """schema 基本结构合法:type=function, name=intent_type, 有 description/parameters/required/strict。"""
    schema = tool_cls.get_openai_tool_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == tool_cls.intent_type
    assert isinstance(schema["function"]["description"], str)
    assert len(schema["function"]["description"]) >= 5
    assert schema["function"]["parameters"]["type"] == "object"
    assert "required" in schema["function"]["parameters"]
    assert schema["function"].get("strict") is True


def _assert_strict(node):
    """递归断言每个 object 节点都有 additionalProperties=false,array.items 也递归。"""
    if node.get("type") == "object":
        assert node.get("additionalProperties") is False, f"object 节点缺 additionalProperties=false: {node}"
        for prop in node.get("properties", {}).values():
            _assert_strict(prop)
    elif node.get("type") == "array":
        _assert_strict(node["items"])


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES, ids=lambda c: c.intent_type)
def test_tool_schema_is_strict(tool_cls):
    """OpenAI strict 模式要求每层 object/array 都有 additionalProperties=false。"""
    schema = tool_cls.get_openai_tool_schema()
    _assert_strict(schema["function"]["parameters"])


# ---------------------------------------------------------------------------
# 显式 enum 测试:ComplianceTool 的 severity 字段必须有 enum
# ---------------------------------------------------------------------------


def test_compliance_tool_severity_has_enum():
    """ComplianceTool 的 severity 参数是 JSON Schema enum(紧急/高/中/低)。"""
    from smart_assistant.tools.compliance_tool import ComplianceTool

    schema = ComplianceTool.get_openai_tool_schema()
    severity_param = schema["function"]["parameters"]["properties"].get("severity")
    assert severity_param is not None, "ComplianceTool 应暴露 severity 字段"
    assert severity_param.get("type") == "string"
    assert "enum" in severity_param, "severity 必须用 JSON Schema enum 限制取值"
    assert set(severity_param["enum"]) == {"紧急", "高", "中", "低"}


# ---------------------------------------------------------------------------
# 显式 risk_level 关联测试:OfficeGenerateTool description 必须提示需要确认
# ---------------------------------------------------------------------------


def test_office_generate_tool_description_mentions_confirmation():
    """OfficeGenerateTool(risk_level=write + require_confirmation)description 必须显式提示需要用户确认。"""
    from smart_assistant.tools.office_generate_tool import OfficeGenerateTool

    assert OfficeGenerateTool.risk_level == "write"
    assert OfficeGenerateTool.require_confirmation is True
    desc = OfficeGenerateTool.get_openai_tool_schema()["function"]["description"]
    assert "确认" in desc or "confirmation" in desc.lower(), (
        f"OfficeGenerateTool description 必须提示用户确认: 实际='{desc}'"
    )


# ---------------------------------------------------------------------------
# Registry lint:ToolRegistry.assert_all_have_openai_schema 必须静默(Task 4 验收)
# ---------------------------------------------------------------------------


def test_registry_assert_all_have_openai_schema_passes():
    """所有 19 个注册工具已实现 schema → registry lint 不抛错。"""
    from smart_assistant.tools.registry import ToolRegistry

    # 应静默通过;若有任何工具未实现 schema 会抛 AssertionError
    ToolRegistry.assert_all_have_openai_schema()


def test_registry_get_openai_tools_returns_all_19():
    """ToolRegistry.get_openai_tools() 返回所有 19 个工具的 schema。"""
    from smart_assistant.tools.registry import ToolRegistry

    schemas = ToolRegistry.get_openai_tools()
    assert len(schemas) == len(ALL_TOOL_CLASSES) == 19
    names = {s["function"]["name"] for s in schemas}
    # 抽样校验关键工具都在
    assert "schedule_query" in names
    assert "compliance_query" in names
    assert "office_generate" in names
    assert "swap_request_create" in names
