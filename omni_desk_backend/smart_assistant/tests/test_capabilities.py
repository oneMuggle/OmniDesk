"""S1 能力注册中心：自动发现、启动自检、权限判定、能力目录。"""

from __future__ import annotations

import json
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError

from smart_assistant.capabilities import (
    LOGIN_ONLY,
    CapabilityRegistry,
    ConfirmPolicy,
    DataScope,
    Toolset,
    ToolSpec,
    capabilities,
    toolset,
    validate_spec,
)
from smart_assistant.capabilities.catalog import default_catalog_path, render_catalog
from smart_assistant.tools.base import BaseTool
from smart_assistant.tools.registry import ToolRegistry

#: 迁移前 apps.py 手工注册的 24 个工具（行为不变的基线）
LEGACY_INTENTS = {
    "schedule_query",
    "personnel_query",
    "knowledge_qa",
    "document_search",
    "event_query",
    "memo_query",
    "memo_create",
    "memo_update",
    "memo_delete",
    "project_status",
    "news_search",
    "meeting_room_query",
    "sensor_query",
    "announcement_query",
    "compliance_query",
    "external_link_query",
    "swap_request_query",
    "swap_request_create",
    "swap_request_decide",
    "office_read",
    "office_generate",
    "spreadsheet_qa",
    "agent_notify",
    "global_search",
}
#: S1 新增的 4 个只读工具
NEW_INTENTS = {
    "notification_query",
    "joint_student_query",
    "communication_thread_query",
    "document_library_query",
}
#: S3-1 新增的 4 个写工具
S3_WRITE_INTENTS = {
    "notification_mark_read",
    "meeting_room_book",
    "meeting_room_cancel",
    "compliance_issue_update_status",
}
ALL_INTENTS = LEGACY_INTENTS | NEW_INTENTS | S3_WRITE_INTENTS
#: 删除类工具默认关闭（S3-1），不注册进 ToolRegistry
DISABLED_BY_DEFAULT = {"memo_delete"}


# ---------------------------------------------------------------------------
# 测试桩
# ---------------------------------------------------------------------------


def _schema(name: str, parameters: dict | None = None, strict: bool = True) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "stub",
            "parameters": parameters
            or {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": strict,
        },
    }


def make_tool(intent: str, risk: str = "read", confirm: bool = False, schema: dict | None = None, scoped=False):
    attrs = {
        "name": intent,
        "description": f"{intent} 描述",
        "intent_type": intent,
        "risk_level": risk,
        "require_confirmation": confirm,
        "execute": lambda self, query=None, context=None, **kw: {"found": True},
        "get_openai_tool_schema": classmethod(lambda cls: schema if schema is not None else _schema(intent)),
    }
    if scoped:
        attrs["build_base_queryset"] = lambda self: None
        attrs["_scope_self"] = lambda self, qs, ctx: qs
    return type(f"Stub_{intent}", (BaseTool,), attrs)


def spec_for(tool_cls, **overrides) -> ToolSpec:
    kwargs = {
        "tool": tool_cls,
        "title": "测试工具",
        "required_permission": LOGIN_ONLY,
        "data_scope": DataScope.OWNER,
    }
    kwargs.update(overrides)
    return ToolSpec(**kwargs)


def make_toolset(name: str, *specs: ToolSpec) -> Toolset:
    return Toolset(name=name, title="测试", app_label="tests", module="tests.ai_tools", specs=tuple(specs))


class FakeToolRegistry:
    def __init__(self):
        self.registered = []

    def register(self, tool):
        self.registered.append(tool.intent_type)


# ---------------------------------------------------------------------------
# 自动发现
# ---------------------------------------------------------------------------


def test_discovered_intents_are_legacy_plus_new():
    intents = {s.intent for s in capabilities.specs()}
    assert intents == ALL_INTENTS
    assert set(ToolRegistry._tools) >= intents - DISABLED_BY_DEFAULT
    assert not set(ToolRegistry._tools) & DISABLED_BY_DEFAULT


def test_registry_uses_same_instance_as_spec():
    for resolved in capabilities.specs():
        if resolved.enabled:
            assert ToolRegistry._tools[resolved.intent] is resolved.tool


def test_legacy_tools_keep_login_only_permission():
    """24 个既有工具原样迁移：不新增权限码，行为不变。"""
    for intent in LEGACY_INTENTS:
        assert capabilities.get(intent).spec.required_permission == LOGIN_ONLY, intent


def test_toolsets_live_in_owning_apps():
    owners = {ts.name: ts.app_label for ts in capabilities.toolsets()}
    assert owners["memos"] == "memos"
    assert owners["schedule"] == "events"
    assert owners["notifications"] == "notifications"
    assert owners["joint_students"] == "joint_students"
    assert owners["document_library"] == "paperless_proxy"
    for ts in capabilities.toolsets():
        assert ts.module == f"{ts.module.split('.')[0]}.ai_tools"


def test_new_tools_are_read_only_and_idempotent():
    for intent in NEW_INTENTS:
        resolved = capabilities.get(intent)
        assert resolved.read_only and resolved.idempotent
        assert resolved.spec.confirm == ConfirmPolicy.NONE


def test_write_tools_all_require_user_confirmation():
    for resolved in capabilities.specs():
        if not resolved.read_only:
            assert resolved.spec.confirm == ConfirmPolicy.USER, resolved.intent
            assert resolved.tool.require_confirmation, resolved.intent


def test_discover_is_rerunnable_and_uses_given_registry():
    registry = CapabilityRegistry()
    fake = FakeToolRegistry()
    registry.discover(tool_registry=fake)
    registry.discover(tool_registry=fake)
    assert len(registry.specs()) == len(capabilities.specs())
    assert len(fake.registered) == 2 * len([s for s in registry.specs() if s.enabled])


def test_load_module_reads_decorated_functions_in_order():
    tool_a = make_tool("s1_order_a")
    tool_b = make_tool("s1_order_b")

    @toolset("second", title="二")
    def second():
        return [spec_for(tool_b)]

    @toolset("first", title="一")
    def first():
        return [spec_for(tool_a)]

    module = SimpleNamespace(__name__="demo.ai_tools", second=second, first=first, helper=lambda: None)
    registry = CapabilityRegistry()
    loaded = registry.load_module(module, "demo")
    assert [ts.name for ts in loaded] == ["second", "first"]
    assert registry.get("s1_order_b").toolset.app_label == "demo"


def test_tool_can_be_referenced_by_dotted_path():
    registry = CapabilityRegistry()
    spec = ToolSpec(
        tool="notifications.ai_tools.NotificationQueryTool",
        title="通知",
        required_permission=LOGIN_ONLY,
        data_scope=DataScope.OWNER,
    )
    registry.register_toolset(make_toolset("dotted", spec))
    assert registry.get("notification_query") is not None


def test_required_permission_cannot_be_omitted():
    with pytest.raises(TypeError):
        ToolSpec(tool=make_tool("s1_missing_perm"), title="x", data_scope=DataScope.OWNER)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# 启动自检
# ---------------------------------------------------------------------------


def _errors(tool_cls, **overrides) -> list[str]:
    return validate_spec(spec_for(tool_cls, **overrides), tool_cls())


def test_valid_read_spec_has_no_errors():
    assert _errors(make_tool("s1_ok")) == []


def test_write_tool_without_confirm_is_rejected():
    errors = _errors(make_tool("s1_write", risk="write", confirm=True))
    assert any("必须声明 confirm" in e for e in errors)


def test_write_tool_confirm_must_match_require_confirmation():
    errors = _errors(make_tool("s1_write2", risk="write", confirm=False), confirm=ConfirmPolicy.USER)
    assert any("require_confirmation 必须为 True" in e for e in errors)


def test_destructive_tool_with_confirm_and_flag_passes():
    tool = make_tool("s1_del", risk="destructive", confirm=True)
    assert _errors(tool, confirm=ConfirmPolicy.USER, feature_flag="SMART_ASSISTANT_ENABLE_DESTRUCTIVE_TOOLS") == []


def test_destructive_tool_must_declare_feature_flag():
    """S3-1：删除类能力默认关闭，自检要求 destructive 工具必须挂开关。"""
    errors = _errors(make_tool("s1_del2", risk="destructive", confirm=True), confirm=ConfirmPolicy.USER)
    assert any("feature_flag" in e for e in errors)


def test_rollback_policy_must_be_known():
    errors = _errors(make_tool("s1_rb", risk="write", confirm=True), confirm=ConfirmPolicy.USER, rollback="magic")
    assert any("rollback 取值无效" in e for e in errors)


def test_destructive_tools_disabled_by_default_and_enabled_by_flag(settings):
    assert capabilities.get("memo_delete").enabled is False
    settings.SMART_ASSISTANT_ENABLE_DESTRUCTIVE_TOOLS = True
    registry = CapabilityRegistry()
    fake = FakeToolRegistry()
    registry.discover(tool_registry=fake)
    assert registry.get("memo_delete").enabled is True
    assert "memo_delete" in fake.registered


def test_s3_write_tools_declare_rollback():
    for intent in S3_WRITE_INTENTS:
        resolved = capabilities.get(intent)
        assert not resolved.read_only and resolved.spec.rollback == "agent_write_log", intent


def test_read_tool_must_not_declare_confirm_or_rollback():
    errors = _errors(make_tool("s1_read"), confirm=ConfirmPolicy.USER, rollback="agent_write_log")
    assert any("只读工具不应声明确认" in e for e in errors)
    assert any("rollback" in e for e in errors)


@pytest.mark.parametrize("perm", [None, "", "view_memo", "Memos.View", "a.b.c"])
def test_permission_format_is_checked(perm):
    errors = _errors(make_tool("s1_perm"), required_permission=perm)
    assert any("required_permission" in e for e in errors)


def test_django_permission_code_is_accepted():
    assert _errors(make_tool("s1_perm_ok"), required_permission="memos.view_memo") == []


def test_invalid_data_scope_and_confirm_values():
    errors = _errors(make_tool("s1_enum"), data_scope="everyone", confirm="maybe")
    assert any("data_scope" in e for e in errors)
    assert any("confirm" in e for e in errors)


def test_scope_data_scope_requires_scope_methods():
    errors = _errors(make_tool("s1_noscope"), data_scope=DataScope.SCOPE)
    assert any("build_base_queryset" in e for e in errors)
    assert _errors(make_tool("s1_scoped", scoped=True), data_scope=DataScope.SCOPE) == []


def test_schema_must_be_strict():
    loose = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "filters": {"type": "object", "properties": {"a": {"type": "string"}}},
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    errors = _errors(make_tool("s1_loose", schema=_schema("s1_loose", loose)))
    assert any("parameters.filters" in e for e in errors)

    errors = _errors(make_tool("s1_nostrict", schema=_schema("s1_nostrict", strict=False)))
    assert any("strict=True" in e for e in errors)


def test_schema_name_must_match_intent():
    errors = _errors(make_tool("s1_name", schema=_schema("other_name")))
    assert any("不一致" in e for e in errors)


def test_register_toolset_raises_improperly_configured():
    registry = CapabilityRegistry()
    bad = spec_for(make_tool("s1_bad", risk="write", confirm=True))
    with pytest.raises(ImproperlyConfigured, match="必须声明 confirm"):
        registry.register_toolset(make_toolset("bad", bad))
    assert registry.specs() == []


def test_duplicate_intent_and_toolset_name_are_rejected():
    registry = CapabilityRegistry()
    tool = make_tool("s1_dup")
    registry.register_toolset(make_toolset("dup", spec_for(tool)))
    with pytest.raises(ImproperlyConfigured, match="toolset 名称重复"):
        registry.register_toolset(make_toolset("dup", spec_for(make_tool("s1_dup_other"))))
    with pytest.raises(ImproperlyConfigured, match="intent 重复"):
        registry.register_toolset(make_toolset("dup2", spec_for(tool)))


def test_empty_or_badly_named_toolset_is_rejected():
    registry = CapabilityRegistry()
    with pytest.raises(ImproperlyConfigured, match="没有声明任何工具"):
        registry.register_toolset(make_toolset("empty"))
    with pytest.raises(ImproperlyConfigured, match="小写蛇形"):
        registry.register_toolset(make_toolset("Bad-Name", spec_for(make_tool("s1_badname"))))


def test_unimportable_tool_is_reported():
    registry = CapabilityRegistry()
    spec = ToolSpec(tool="nope.missing.Tool", title="x", required_permission=LOGIN_ONLY, data_scope=DataScope.OWNER)
    with pytest.raises(ImproperlyConfigured, match="无法实例化"):
        registry.register_toolset(make_toolset("broken", spec))


# ---------------------------------------------------------------------------
# feature_flag（预留字段）
# ---------------------------------------------------------------------------


def test_feature_flag_off_keeps_tool_unregistered(settings):
    settings.S1_TEST_FLAG = False
    registry = CapabilityRegistry()
    fake = FakeToolRegistry()
    tool = make_tool("s1_flagged")
    registry.register_toolset(make_toolset("flagged", spec_for(tool, feature_flag="S1_TEST_FLAG")))
    for resolved in registry.specs():
        if resolved.enabled:
            fake.register(resolved.tool)
    assert fake.registered == []
    assert registry.specs(include_disabled=False) == []
    assert registry.is_permitted("s1_flagged", SimpleNamespace(is_authenticated=True)) is False


def test_feature_flag_on_registers_tool(settings):
    settings.S1_TEST_FLAG = True
    registry = CapabilityRegistry()
    registry.register_toolset(
        make_toolset("flagged", spec_for(make_tool("s1_flagged_on"), feature_flag="S1_TEST_FLAG"))
    )
    assert registry.get("s1_flagged_on").enabled is True


# ---------------------------------------------------------------------------
# 权限判定
# ---------------------------------------------------------------------------


@pytest.fixture
def gated_tool(monkeypatch):
    """临时往全局注册中心 + ToolRegistry 放一个需要 memos.view_memo 的工具。"""
    tool_cls = make_tool("s1_gated")
    registry = CapabilityRegistry()
    (resolved,) = registry.register_toolset(
        make_toolset("gated", spec_for(tool_cls, required_permission="memos.view_memo"))
    )
    monkeypatch.setitem(capabilities._specs, "s1_gated", resolved)
    monkeypatch.setitem(ToolRegistry._tools, "s1_gated", resolved.tool)
    return resolved.tool


@pytest.fixture
def plain_user(db, django_user_model):
    return django_user_model.objects.create_user(username="s1_plain", password="x")


@pytest.fixture
def memo_viewer(db, django_user_model):
    from django.contrib.auth.models import Permission

    user = django_user_model.objects.create_user(username="s1_viewer", password="x")
    user.user_permissions.add(Permission.objects.get(content_type__app_label="memos", codename="view_memo"))
    return django_user_model.objects.get(pk=user.pk)  # 重新取出以清空权限缓存


def test_is_permitted_matrix(gated_tool, plain_user, memo_viewer, django_user_model):
    from django.contrib.auth.models import AnonymousUser

    admin = django_user_model.objects.create_superuser(username="s1_admin", password="x")
    assert capabilities.is_permitted("s1_gated", plain_user) is False
    assert capabilities.is_permitted("s1_gated", memo_viewer) is True
    assert capabilities.is_permitted("s1_gated", admin) is True
    assert capabilities.is_permitted("s1_gated", AnonymousUser()) is False
    assert capabilities.is_permitted("s1_gated", None) is False
    # 未声明的工具与 LOGIN_ONLY 工具放行
    assert capabilities.is_permitted("not_declared_intent", None) is True
    assert capabilities.is_permitted("memo_query", plain_user) is True


def test_get_tool_for_user_respects_permission(gated_tool, plain_user, memo_viewer):
    assert ToolRegistry.get_tool_for_user("s1_gated", plain_user) is None
    assert ToolRegistry.get_tool_for_user("s1_gated", memo_viewer) is gated_tool
    assert ToolRegistry.get_tool_for_user("memo_query", plain_user) is not None


def test_get_openai_tools_hides_unpermitted_tools(gated_tool, plain_user, memo_viewer):
    names_plain = {t["function"]["name"] for t in ToolRegistry.get_openai_tools(plain_user)}
    names_viewer = {t["function"]["name"] for t in ToolRegistry.get_openai_tools(memo_viewer)}
    assert "s1_gated" not in names_plain
    assert "s1_gated" in names_viewer
    assert names_plain >= (ALL_INTENTS - DISABLED_BY_DEFAULT)
    assert not names_plain & DISABLED_BY_DEFAULT


def test_function_tool_chain_blocks_unpermitted_tool(gated_tool, plain_user, memo_viewer, settings):
    from smart_assistant.agent.tool_chain_executor import execute_tool_chain

    settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = False
    plan = [{"tool": "s1_gated", "params": {}}]
    denied = execute_tool_chain(plan, "q", context={"user": plain_user})
    allowed = execute_tool_chain(plan, "q", context={"user": memo_viewer})
    assert denied[0]["success"] is False
    assert allowed[0]["success"] is True


def test_missing_permissions_reports_unknown_codes(db, monkeypatch):
    registry = CapabilityRegistry()
    registry.register_toolset(
        make_toolset(
            "perm_check",
            spec_for(make_tool("s1_real_perm"), required_permission="memos.view_memo"),
            spec_for(make_tool("s1_fake_perm"), required_permission="memos.fly_memo"),
        )
    )
    assert registry.missing_permissions() == ["[s1_fake_perm] memos.fly_memo"]


@pytest.mark.django_db
def test_all_declared_permissions_exist():
    assert capabilities.missing_permissions() == []


# ---------------------------------------------------------------------------
# MCP 注解与能力目录
# ---------------------------------------------------------------------------


def test_annotations_follow_risk_level():
    read = capabilities.get("memo_query").annotations()
    delete = capabilities.get("memo_delete").annotations()
    rag = capabilities.get("knowledge_qa").annotations()
    assert read == {
        "title": "查询备忘录",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    assert delete["destructiveHint"] is True and delete["readOnlyHint"] is False
    assert delete["idempotentHint"] is False
    assert rag["openWorldHint"] is True


def test_catalog_lists_every_tool_once():
    content = render_catalog(capabilities)
    for resolved in capabilities.specs():
        # 明细表每个工具一行（行首为 intent 列）
        assert content.count(f"\n| `{resolved.intent}` |") == 1, resolved.intent
    assert "本文件由代码自动生成" in content


def test_committed_catalog_matches_code():
    """能力目录必须与代码一致；失败时运行 python manage.py ai_capabilities --write。"""
    path = default_catalog_path()
    if not path.exists():  # 仅打包后端镜像、没有 docs 目录时跳过
        pytest.skip(f"未找到 {path}")
    assert path.read_text(encoding="utf-8") == render_catalog(capabilities)


@pytest.mark.django_db
def test_command_write_check_and_json(tmp_path):
    target = tmp_path / "catalog.md"
    call_command("ai_capabilities", "--write", "--path", str(target), stdout=StringIO())
    assert target.read_text(encoding="utf-8") == render_catalog(capabilities)

    out = StringIO()
    call_command("ai_capabilities", "--check", "--path", str(target), stdout=out)
    assert "一致" in out.getvalue()

    target.write_text("过期内容", encoding="utf-8")
    with pytest.raises(CommandError):
        call_command("ai_capabilities", "--check", "--path", str(target), stdout=StringIO(), stderr=StringIO())

    out = StringIO()
    call_command("ai_capabilities", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert {item["intent"] for item in payload} == ALL_INTENTS
    assert all("annotations" in item for item in payload)

    out = StringIO()
    call_command("ai_capabilities", stdout=out)
    assert f"{len(capabilities.specs())} 个工具" in out.getvalue()


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("我有几条未读通知", ["notification_query"]),
        ("文档库里有没有采购合同", ["document_library_query"]),
        ("我带的联培生有哪些", ["joint_student_query"]),
        ("交流区最近在讨论什么", ["communication_thread_query"]),
    ],
)
def test_new_intent_keywords_do_not_trigger_multi_tool(query, expected):
    """新工具的关键词经子串消解后应只命中自身，不误触发多工具链。"""
    from smart_assistant.agent.tool_chain_planner import _resolve_intent_overlap

    schemas = [{"name": name} for name in ToolRegistry._tools]
    assert _resolve_intent_overlap(query, schemas) == expected
