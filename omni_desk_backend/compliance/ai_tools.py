"""合规模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import (
    LOGIN_ONLY,
    ROLLBACK_AGENT_WRITE_LOG,
    ConfirmPolicy,
    DataScope,
    QuickPrompt,
    ToolSpec,
    toolset,
)


@toolset(
    "compliance",
    title="合规",
    routes=(r"^/control-panel/compliance",),
    quick_prompts=(
        QuickPrompt("合规待办", "我有哪些待处理的合规问题？", routes=(r"^/$", r"^/control-panel/compliance")),
        QuickPrompt("逾期整改", "有哪些已经逾期的整改项？"),
    ),
)
def compliance_tools():
    from smart_assistant.tools.compliance_tool import ComplianceTool
    from smart_assistant.tools.compliance_write_tools import ComplianceStatusUpdateTool

    return [
        ToolSpec(
            tool=ComplianceTool,
            title="查询合规问题",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
        ToolSpec(
            tool=ComplianceStatusUpdateTool,
            title="更新合规问题状态",
            # 与页面一致：管理员或项目负责人（ComplianceChecker.can_modify_issue）
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.MODULE,
            confirm=ConfirmPolicy.USER,
            rollback=ROLLBACK_AGENT_WRITE_LOG,
        ),
    ]
