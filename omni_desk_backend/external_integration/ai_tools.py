"""外部集成模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset


@toolset("external_links", title="内网外链")
def external_link_tools():
    from smart_assistant.tools.external_link_tool import ExternalLinkTool

    return [
        ToolSpec(
            tool=ExternalLinkTool,
            title="查询内网外链",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
    ]
