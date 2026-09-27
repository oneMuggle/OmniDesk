"""人员模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset


@toolset("personnel", title="人员")
def personnel_tools():
    from smart_assistant.tools.personnel_tool import PersonnelTool

    return [
        ToolSpec(
            tool=PersonnelTool,
            title="查询人员",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
    ]
