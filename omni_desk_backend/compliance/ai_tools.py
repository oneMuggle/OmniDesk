"""合规模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset, QuickPrompt


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

    return [
        ToolSpec(
            tool=ComplianceTool,
            title="查询合规问题",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
    ]
