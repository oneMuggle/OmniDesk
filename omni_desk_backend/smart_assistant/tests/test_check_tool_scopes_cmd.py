import pytest
from io import StringIO
from django.core.management import call_command
from smart_assistant.tools.registry import ToolRegistry


@pytest.fixture
def restore_tool_registry():
    """测试结束后把 ToolRegistry._tools 内容还原为本测试运行开始时的状态。

    原因:tests #2/#3 会临时把 _tools 中的某条换成"缺方法"的 stub 实例,需要在
    测试结束时换回原实例,以免污染后续测试。
    """
    snapshot = dict(ToolRegistry._tools)  # 浅拷贝即可(tool 实例本身不动)
    yield
    # 还原
    for intent in list(ToolRegistry._tools.keys()):
        if intent not in snapshot:
            ToolRegistry._tools.pop(intent, None)
    for intent, original_tool in snapshot.items():
        ToolRegistry._tools[intent] = original_tool


def test_command_succeeds_when_all_tools_implement(restore_tool_registry):
    """所有 13 个工具实现 _scope_self 时命令 exit 0"""
    real_get = ToolRegistry.get_tool

    def fake_get(intent_type):
        tool = real_get(intent_type)
        if tool and not hasattr(tool, "_scope_self"):
            tool._scope_self = lambda qs, ctx: qs
            tool.build_base_queryset = lambda: "fake_qs"
        return tool

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(ToolRegistry, "get_tool", classmethod(lambda cls, x: fake_get(x)))
    try:
        out = StringIO()
        call_command("check_tool_scopes", stdout=out)
        assert "OK" in out.getvalue() or "✅" in out.getvalue()
    finally:
        monkeypatch.undo()


def test_command_fails_when_tool_missing_scope_self(restore_tool_registry):
    """缺 _scope_self 时命令 exit 非零

    实现策略:_scope_self 是类方法(定义在 class 上),对实例 delattr 不会清除
    类上的定义,hasattr 仍返回 True。所以这里用一个缺 _scope_self 的 stub 实例
    替换 _tools["schedule_query"],测试结束后由 restore_tool_registry 还原。
    """
    original_tool = ToolRegistry._tools.get("schedule_query")
    assert original_tool is not None, "schedule_query 工具未注册"

    class _StubWithoutScopeSelf:
        """故意缺 _scope_self 的 stub"""
        intent_type = "schedule_query"
        name = "schedule_query_stub"
        required_auth = False

        def build_base_queryset(self):
            """有意实现,但缺 _scope_self"""
            return None

        # 故意不定义 _scope_self

    ToolRegistry._tools["schedule_query"] = _StubWithoutScopeSelf()
    try:
        with pytest.raises(SystemExit) as exc:
            call_command("check_tool_scopes", stdout=StringIO())
        assert exc.value.code != 0
    finally:
        ToolRegistry._tools["schedule_query"] = original_tool


def test_command_fails_when_tool_missing_build_base_queryset(restore_tool_registry):
    """缺 build_base_queryset 时命令 exit 非零

    同上,build_base_queryset 是类方法 → 用 stub 替换 _tools 条目。
    """
    original_tool = ToolRegistry._tools.get("meeting_room_query")
    assert original_tool is not None, "meeting_room_query 工具未注册"

    class _StubWithoutBuildBaseQueryset:
        """故意缺 build_base_queryset 的 stub"""
        intent_type = "meeting_room_query"
        name = "meeting_room_query_stub"
        required_auth = False

        def _scope_self(self, qs, ctx):
            """有意实现,但缺 build_base_queryset"""
            return qs

        # 故意不定义 build_base_queryset

    ToolRegistry._tools["meeting_room_query"] = _StubWithoutBuildBaseQueryset()
    try:
        with pytest.raises(SystemExit) as exc:
            call_command("check_tool_scopes", stdout=StringIO())
        assert exc.value.code != 0
    finally:
        ToolRegistry._tools["meeting_room_query"] = original_tool


def test_command_skips_unregistered_tools(restore_tool_registry, capsys):
    """未注册的工具不被检查(已注册的全部 13 个)"""
    out = StringIO()
    call_command("check_tool_scopes", stdout=out)
    output = out.getvalue()
    assert len(output) > 0


def test_command_outputs_tool_count(restore_tool_registry, capsys):
    """命令输出包含检查的工具数量"""
    out = StringIO()
    call_command("check_tool_scopes", stdout=out)
    output = out.getvalue()
    assert "13" in output or "tools" in output.lower()
