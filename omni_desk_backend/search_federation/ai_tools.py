"""联邦搜索模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset


@toolset("search", title="跨模块检索")
def search_tools():
    from smart_assistant.tools.global_search_tool import GlobalSearchTool

    return [
        ToolSpec(
            tool=GlobalSearchTool,
            title="跨模块检索",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.DELEGATED,
        ),
    ]
