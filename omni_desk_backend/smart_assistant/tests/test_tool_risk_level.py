"""工具权限分级测试

覆盖 tools/base.py 的风险等级(risk_level)机制:
- 风险等级枚举常量(read/write/destructive)
- BaseTool 默认值(risk_level="read", require_confirmation=False)
- get_schema() 输出包含 risk_level 字段
- apps.py 注册的全部 13 个工具:risk_level 取值合法、显式声明、schema 含字段
- 语义一致性:read 级工具不得要求二次确认

注:13 个工具均为只读查询工具,当前全部为 "read";write/destructive 的
语义与确认流程约定见 BaseTool.risk_level docstring,为未来写操作工具预留。
"""

import pytest

from smart_assistant.tools.base import (
    RISK_LEVEL_DESTRUCTIVE,
    RISK_LEVEL_READ,
    RISK_LEVEL_WRITE,
    VALID_RISK_LEVELS,
    BaseTool,
)
from smart_assistant.tools.registry import ToolRegistry

# apps.py ready() 注册的 13 个工具(intent_type → 工具类),用于全量校验
from smart_assistant.tools.announcement_tool import AnnouncementTool
from smart_assistant.tools.compliance_tool import ComplianceTool
from smart_assistant.tools.document_tool import DocumentTool
from smart_assistant.tools.event_tool import EventTool
from smart_assistant.tools.external_link_tool import ExternalLinkTool
from smart_assistant.tools.meeting_room_tool import MeetingRoomTool
from smart_assistant.tools.memo_tool import MemoTool
from smart_assistant.tools.news_tool import NewsTool
from smart_assistant.tools.office_generate_tool import OfficeGenerateTool
from smart_assistant.tools.personnel_tool import PersonnelTool
from smart_assistant.tools.project_tool import ProjectTool
from smart_assistant.tools.rag_tool import RAGTool
from smart_assistant.tools.schedule_tool import ScheduleTool
from smart_assistant.tools.sensor_tool import SensorTool

ALL_TOOL_CLASSES = [
    ScheduleTool,
    PersonnelTool,
    RAGTool,
    DocumentTool,
    EventTool,
    MemoTool,
    ProjectTool,
    NewsTool,
    MeetingRoomTool,
    SensorTool,
    AnnouncementTool,
    ComplianceTool,
    ExternalLinkTool,
]


class _MinimalTool(BaseTool):
    """最小 BaseTool 子类:不声明 risk_level,验证基类默认值"""

    name = "minimal_tool"
    description = "最小测试工具"
    intent_type = "minimal_intent"

    def execute(self, query: str, context=None) -> dict:
        return {"found": True}


# ---------------------------------------------------------------------------
# 风险等级枚举常量
# ---------------------------------------------------------------------------


class TestRiskLevelConstants:
    def test_valid_risk_levels_enum(self):
        """VALID_RISK_LEVELS 恰好包含 read/write/destructive"""
        assert VALID_RISK_LEVELS == {"read", "write", "destructive"}

    def test_constant_values(self):
        """常量与字符串值一致(防止重命名引入隐性不一致)"""
        assert RISK_LEVEL_READ == "read"
        assert RISK_LEVEL_WRITE == "write"
        assert RISK_LEVEL_DESTRUCTIVE == "destructive"


# ---------------------------------------------------------------------------
# BaseTool 默认值与 schema
# ---------------------------------------------------------------------------


class TestBaseToolRiskDefaults:
    def test_default_risk_level_is_read(self):
        """未声明 risk_level 的子类继承默认值 "read"(fail-safe:最低权限)"""
        assert _MinimalTool().risk_level == "read"

    def test_default_require_confirmation_is_false(self):
        """默认不要求二次确认"""
        assert _MinimalTool().require_confirmation is False

    def test_schema_contains_risk_level(self):
        """get_schema() 输出必须包含 risk_level 字段"""
        schema = _MinimalTool().get_schema()
        assert "risk_level" in schema
        assert schema["risk_level"] == "read"

    def test_schema_keeps_legacy_fields(self):
        """原有字段(name/description/intent_type)不受新增字段影响"""
        schema = _MinimalTool().get_schema()
        assert schema["name"] == "minimal_tool"
        assert schema["description"] == "最小测试工具"
        assert schema["intent_type"] == "minimal_intent"


# ---------------------------------------------------------------------------
# 全部注册工具的全量校验
# ---------------------------------------------------------------------------


class TestAllToolsRiskLevel:
    @pytest.mark.parametrize(
        "tool_cls",
        ALL_TOOL_CLASSES,
        ids=lambda cls: cls.__name__,
    )
    def test_risk_level_is_valid(self, tool_cls):
        """每个工具的 risk_level 必须是合法枚举值"""
        tool = tool_cls()
        assert tool.risk_level in VALID_RISK_LEVELS, (
            f"{tool_cls.__name__}.risk_level={tool.risk_level!r} 不在 {VALID_RISK_LEVELS} 中"
        )

    @pytest.mark.parametrize(
        "tool_cls",
        ALL_TOOL_CLASSES,
        ids=lambda cls: cls.__name__,
    )
    def test_risk_level_explicitly_declared(self, tool_cls):
        """每个工具必须显式声明 risk_level(而非仅继承基类默认值),

        便于代码评审时一眼确认副作用边界。
        """
        assert "risk_level" in tool_cls.__dict__, (
            f"{tool_cls.__name__} 未显式声明 risk_level 类属性"
        )

    @pytest.mark.parametrize(
        "tool_cls",
        ALL_TOOL_CLASSES,
        ids=lambda cls: cls.__name__,
    )
    def test_listed_tools_are_read_only(self, tool_cls):
        """当前 ALL_TOOL_CLASSES 列出的工具均为只读查询工具,必须标注为 "read"。

        注意:此断言仅覆盖显式枚举的工具。新增写/破坏性工具若未加入列表,
        不会触发本测试失败——必须另写显式断言(如 test_office_generate_is_write)
        防止出现"全 read"的假象。
        """
        assert tool_cls().risk_level == "read"

    @pytest.mark.parametrize(
        "tool_cls",
        ALL_TOOL_CLASSES,
        ids=lambda cls: cls.__name__,
    )
    def test_schema_exposes_risk_level(self, tool_cls):
        """每个工具的 get_schema() 输出包含合法的 risk_level"""
        schema = tool_cls().get_schema()
        assert "risk_level" in schema
        assert schema["risk_level"] in VALID_RISK_LEVELS


# ---------------------------------------------------------------------------
# 语义一致性约定
# ---------------------------------------------------------------------------


class TestRiskLevelSemantics:
    def test_read_tools_must_not_require_confirmation(self):
        """约定:read 级工具无副作用,不得要求二次确认

        (require_confirmation 仅对 write/destructive 有意义)
        """
        for tool_cls in ALL_TOOL_CLASSES:
            tool = tool_cls()
            if tool.risk_level == RISK_LEVEL_READ:
                assert tool.require_confirmation is False, (
                    f"{tool_cls.__name__} 为 read 级却要求确认"
                )

    def test_registry_tools_have_valid_risk_level(self):
        """ToolRegistry 中实际注册的工具(由 apps.ready 写入)全部合法

        防止注册了未遵循分级约定的工具实例。
        """
        registered = list(ToolRegistry._tools.values())
        # 至少包含 apps.py 注册的 13 个工具
        assert len(registered) >= 13
        for tool in registered:
            assert tool.risk_level in VALID_RISK_LEVELS, (
                f"注册工具 {getattr(tool, 'name', tool)!r} 的 risk_level 非法"
            )
            assert tool.get_schema()["risk_level"] == tool.risk_level

    def test_office_generate_is_write(self):
        """显式守卫:OfficeGenerateTool 是写操作工具,必须声明 risk_level="write"。

        ALL_TOOL_CLASSES 中仅枚举 read 级工具,因此该 write 级工具不会被
        test_listed_tools_are_read_only 覆盖;若此处声明被意外改为 "read",
        二次确认流程会被绕过,造成真实写操作无确认即执行的隐患。
        """
        tool = OfficeGenerateTool()
        assert tool.risk_level == "write", (
            f"OfficeGenerateTool.risk_level={tool.risk_level!r},必须为 'write'"
        )
        assert tool.require_confirmation is True, (
            "write 级工具必须要求二次确认"
        )
