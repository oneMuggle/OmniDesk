"""项目模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset


@toolset("projects", title="项目")
def project_tools():
    from smart_assistant.tools.project_tool import ProjectTool

    return [
        ToolSpec(
            tool=ProjectTool,
            title="查询项目状态",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
    ]
