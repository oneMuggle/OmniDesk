"""合规模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset


@toolset("compliance", title="合规")
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
