"""新闻模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset


@toolset("news", title="新闻")
def news_tools():
    from smart_assistant.tools.news_tool import NewsTool

    return [
        ToolSpec(
            tool=NewsTool,
            title="搜索新闻",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
    ]
