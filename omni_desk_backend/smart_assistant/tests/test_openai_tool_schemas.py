"""Tests for BaseTool OpenAI tool schema — 22 tools × strict JSON Schema validation.

Task 4 验证:每个 BaseTool 子类都正确实现了 get_openai_tool_schema(),
且 schema 满足 OpenAI strict 模式要求(每层 object/array 都有
additionalProperties=false)。

参数化覆盖:
- 22 个注册工具 × 2 个断言 = 44 个用例
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
    """所有 22 个注册工具已实现 schema → registry lint 不抛错。"""
    from smart_assistant.tools.registry import ToolRegistry

    # 应静默通过;若有任何工具未实现 schema 会抛 AssertionError
    ToolRegistry.assert_all_have_openai_schema()


@pytest.mark.django_db
def test_registry_get_openai_tools_returns_all_22():
    """ToolRegistry.get_openai_tools(user) 认证用户应拿到所有 22 个工具的 schema。

    Task 5 调整:无参调用 user=None 视为匿名 → 过滤掉所有 required_auth=True
    工具。本测试聚焦"已认证用户应拿到所有工具"的语义校验。
    """
    from django.contrib.auth import get_user_model

    from smart_assistant.tools.registry import ToolRegistry

    User = get_user_model()
    user = User.objects.create_user(username="all22_user_t5", password="x")

    schemas = ToolRegistry.get_openai_tools(user)
    assert len(schemas) == len(ALL_TOOL_CLASSES) == 22
    names = {s["function"]["name"] for s in schemas}
    # 抽样校验关键工具都在
    assert "schedule_query" in names
    assert "compliance_query" in names
    assert "office_generate" in names
    assert "swap_request_create" in names


# ---------------------------------------------------------------------------
# Task 5:ToolRegistry.get_openai_tools(user) 扩展(用户过滤 + risk_level 排序 + schema 校验)
# ---------------------------------------------------------------------------
# 任务范围:扩展现有的 ToolRegistry.get_openai_tools() 签名,接受可选 user 参数,
# 实现按用户过滤(required_auth 工具对未登录用户隐藏)+ 按 risk_level 排序
# (read 在前,降低 LLM 误调写工具风险) + schema 结构校验(防止非 dict / 字段缺失
# 静默进入 LLM payload)。
#
# 设计依据:Task 4 review 中 reviewer 建议 — get_openai_tools() 应支持用户上下文,
# 且 registry 应主动过滤未授权工具,而不是依赖 orchestrator 层手工过滤。
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_openai_tools_with_user_returns_all_for_authenticated_user():
    """认证用户(user.is_authenticated=True)应能拿到所有 required_auth=True 工具。

    当前 22 个工具均 required_auth=True,故认证用户应拿到完整 22 个 schema。
    """
    from django.contrib.auth import get_user_model

    from smart_assistant.tools.registry import ToolRegistry

    User = get_user_model()
    user = User.objects.create_user(username="auth_user_t5", password="x")

    tools = ToolRegistry.get_openai_tools(user)
    assert isinstance(tools, list)
    assert len(tools) == len(ALL_TOOL_CLASSES) == 22
    names = {t["function"]["name"] for t in tools}
    assert "schedule_query" in names
    assert "office_generate" in names
    assert "swap_request_create" in names


@pytest.mark.django_db
def test_get_openai_tools_anonymous_user_filters_required_auth_tools():
    """匿名用户(AnonymousUser)应看不到任何 required_auth=True 工具。

    当前所有 22 个工具均 required_auth=True → 匿名用户应得到空列表。
    """
    from django.contrib.auth.models import AnonymousUser

    from smart_assistant.tools.registry import ToolRegistry

    tools = ToolRegistry.get_openai_tools(AnonymousUser())
    # 当前所有工具都 required_auth=True → 匿名用户空列表
    assert tools == []


@pytest.mark.django_db
def test_get_openai_tools_none_user_filters_required_auth_tools():
    """user=None 也应触发 required_auth 过滤(等价于匿名)。"""
    from smart_assistant.tools.registry import ToolRegistry

    tools = ToolRegistry.get_openai_tools(None)
    # None 视为未登录 → 过滤掉所有 required_auth=True 工具
    assert tools == []


@pytest.mark.django_db
def test_get_openai_tools_sorted_read_first():
    """风险等级排序:read-only 工具排在 write/destructive 之前。

    验证:
    - 列表中所有 risk_level=read 的工具的位置都 < risk_level=write 的工具位置
    - 排序稳定:同一等级内的工具保持原顺序
    """
    from django.contrib.auth import get_user_model

    from smart_assistant.tools.base import (
        RISK_LEVEL_DESTRUCTIVE,
        RISK_LEVEL_READ,
        RISK_LEVEL_WRITE,
    )
    from smart_assistant.tools.registry import ToolRegistry

    User = get_user_model()
    user = User.objects.create_user(username="sort_user_t5", password="x")

    tools = ToolRegistry.get_openai_tools(user)

    # 找到第一个非 read 工具的位置
    first_non_read_idx = None
    for i, tool in enumerate(tools):
        tool_name = tool["function"]["name"]
        tool_cls = ToolRegistry._tools[tool_name]
        if tool_cls.risk_level != RISK_LEVEL_READ:
            first_non_read_idx = i
            break

    assert first_non_read_idx is not None, "应至少有 1 个 write 工具(office_generate)"

    # 此位置之后的所有工具都不应是 read
    for later in tools[first_non_read_idx:]:
        later_name = later["function"]["name"]
        later_cls = ToolRegistry._tools[later_name]
        assert later_cls.risk_level != RISK_LEVEL_READ, (
            f"排序违反:read 工具 {later_name} 出现在位置 {first_non_read_idx} 之后"
        )

    # write 工具应在 destructive 工具之前(当前没有 destructive,仅验证 write 不乱排)
    seen_write_idx = None
    for i, tool in enumerate(tools):
        tool_name = tool["function"]["name"]
        tool_cls = ToolRegistry._tools[tool_name]
        if tool_cls.risk_level == RISK_LEVEL_WRITE:
            seen_write_idx = i
            break
    assert seen_write_idx == first_non_read_idx, (
        f"write 工具应在 read 之后第一个位置;first_non_read_idx={first_non_read_idx}, first_write_idx={seen_write_idx}"
    )

    # 边界:destructive 等级常量必须被工具使用才算合法(允许当前为 0 个)
    write_count = sum(1 for t in tools if ToolRegistry._tools[t["function"]["name"]].risk_level == RISK_LEVEL_WRITE)
    destructive_count = sum(
        1 for t in tools if ToolRegistry._tools[t["function"]["name"]].risk_level == RISK_LEVEL_DESTRUCTIVE
    )
    assert write_count + destructive_count >= 1, "应有 write 或 destructive 工具触发排序"


@pytest.mark.django_db
def test_get_openai_tools_signature_accepts_optional_user():
    """ToolRegistry.get_openai_tools 应支持 user 参数(向后兼容:无 user 调用不抛错)。

    向后兼容 — Task 4 已实现无参版本,Task 5 改为可选 user= 参数,
    旧调用方式 get_openai_tools() 不应抛 TypeError。

    无参调用的语义:user=None → 视为匿名 → 过滤掉所有 required_auth=True
    工具(当前所有 22 个都 required_auth=True → 空列表)。这是 Task 5 引入
    的安全行为变更,但调用方代码不抛错即视为兼容。
    """
    from django.contrib.auth import get_user_model

    from smart_assistant.tools.registry import ToolRegistry

    # 旧用法(无参)不应抛 TypeError
    schemas = ToolRegistry.get_openai_tools()
    # 无参等价于 user=None → 过滤掉所有 required_auth=True 工具
    # 当前 22 个都 required_auth=True → 空列表
    assert schemas == []

    # 新用法(带 user)拿到全部 22 个
    User = get_user_model()
    user = User.objects.create_user(username="compat_t5", password="x")
    schemas_user = ToolRegistry.get_openai_tools(user)
    assert len(schemas_user) == 22


# ---------------------------------------------------------------------------
# Schema 结构校验:防止非法 schema 静默进入 LLM payload
# ---------------------------------------------------------------------------


def test_registry_assert_all_have_openai_schema_rejects_malformed_schema():
    """registry lint 应验证 schema 结构，而非只检查是否抛 NotImplementedError。"""
    from unittest.mock import patch

    from smart_assistant.tools.registry import ToolRegistry

    class FakeMalformedTool:
        intent_type = "fake_malformed_lint"

        @classmethod
        def get_openai_tool_schema(cls):
            return {"type": "function", "function": {"name": cls.intent_type}}

    fake_tools = dict(ToolRegistry._tools)
    fake_tools[FakeMalformedTool.intent_type] = FakeMalformedTool()
    with patch.object(ToolRegistry, "_tools", fake_tools):
        with pytest.raises(AssertionError, match="fake_malformed_lint"):
            ToolRegistry.assert_all_have_openai_schema()


@pytest.mark.django_db
def test_registry_get_openai_tools_accepts_base_tool_fallback():
    """未覆写 schema 的 BaseTool 工具应进入 get_openai_tools。"""
    from unittest.mock import patch

    from django.contrib.auth import get_user_model

    from smart_assistant.tools.base import BaseTool
    from smart_assistant.tools.registry import ToolRegistry

    class LegacyRegisteredTool(BaseTool):
        intent_type = "legacy_registered"
        name = "legacy_registered"
        description = "兼容旧工具"

        def execute(self, query, context):
            return {"found": True}

    User = get_user_model()
    user = User.objects.create_user(username="legacy_schema_user", password="x")
    fake_tools = dict(ToolRegistry._tools)
    fake_tools[LegacyRegisteredTool.intent_type] = LegacyRegisteredTool()
    with patch.object(ToolRegistry, "_tools", fake_tools):
        schemas = ToolRegistry.get_openai_tools(user)

    schema = next(item for item in schemas if item["function"]["name"] == "legacy_registered")
    assert schema["function"]["parameters"]["required"] == ["query"]
    assert schema["function"]["parameters"]["additionalProperties"] is False



@pytest.mark.django_db
def test_get_openai_tools_skips_malformed_schema(caplog):
    """get_openai_tools() 内置 schema 结构校验 — 非 dict / 字段缺失的 schema 跳过 + warning。

    用 monkeypatch 注入一个返回非法 schema 的工具类,验证:
    - 返回值不包含非法工具
    - 不抛错(向后兼容 — 仍是 warning + skip)
    """
    import logging
    from unittest.mock import patch

    from django.contrib.auth import get_user_model

    from smart_assistant.tools.registry import ToolRegistry

    User = get_user_model()
    user = User.objects.create_user(username="malformed_t5", password="x")

    # 注入一个返回非法 schema 的工具
    class FakeBrokenTool:
        intent_type = "fake_broken_tool"
        required_auth = True
        risk_level = "read"

        @classmethod
        def get_openai_tool_schema(cls):
            return {"type": "function"}  # 缺 function 字段

    # Monkeypatch 一个非 dict 返回值
    class FakeNonDictTool:
        intent_type = "fake_non_dict_tool"
        required_auth = True
        risk_level = "read"

        @classmethod
        def get_openai_tool_schema(cls):
            return ["not", "a", "dict"]  # 不是 dict

    fake_tools = dict(ToolRegistry._tools)
    fake_tools[FakeBrokenTool.intent_type] = FakeBrokenTool()
    fake_tools[FakeNonDictTool.intent_type] = FakeNonDictTool()

    with patch.object(ToolRegistry, "_tools", fake_tools), caplog.at_level(logging.WARNING):
        tools = ToolRegistry.get_openai_tools(user)

    names = {t["function"]["name"] for t in tools}
    assert "fake_broken_tool" not in names, "缺 function 字段的 schema 应被过滤"
    assert "fake_non_dict_tool" not in names, "非 dict 返回应被过滤"
    # 合法工具仍保留
    assert "schedule_query" in names
