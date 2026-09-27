"""智能助手自带的通用 AI 工具声明（知识库、办公文件）。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import ConfirmPolicy, DataScope, LOGIN_ONLY, ToolSpec, toolset


@toolset("knowledge", title="知识库")
def knowledge_tools():
    from smart_assistant.tools.rag_tool import RAGTool

    return [
        ToolSpec(
            tool=RAGTool,
            title="知识库问答",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.KNOWLEDGE,
            open_world=True,
        ),
    ]


@toolset("office", title="办公文件")
def office_tools():
    from smart_assistant.tools.office_read_tool import OfficeReadTool
    from smart_assistant.tools.spreadsheet_tool import SpreadsheetTool
    from smart_assistant.tools.office_generate_tool import OfficeGenerateTool

    return [
        ToolSpec(
            tool=OfficeReadTool,
            title="读取附件内容",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.ATTACHMENT,
        ),
        ToolSpec(
            tool=SpreadsheetTool,
            title="表格问答",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.ATTACHMENT,
        ),
        ToolSpec(
            tool=OfficeGenerateTool,
            title="生成 Word 文档",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.OWNER,
            confirm=ConfirmPolicy.USER,
        ),
    ]
