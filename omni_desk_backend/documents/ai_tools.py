"""公文与模板的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset


@toolset("documents", title="公文与模板")
def document_tools():
    from smart_assistant.tools.document_tool import DocumentTool

    return [
        ToolSpec(
            tool=DocumentTool,
            title="搜索公文",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
    ]
