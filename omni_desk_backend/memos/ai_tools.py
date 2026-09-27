"""备忘录的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import ConfirmPolicy, DataScope, LOGIN_ONLY, ToolSpec, toolset, QuickPrompt


@toolset(
    "memos",
    title="备忘录",
    routes=(r"^/memos",),
    quick_prompts=(
        QuickPrompt("我的备忘录", "我最近的备忘录有哪些？", routes=(r"^/$", r"^/memos")),
        QuickPrompt("即将提醒", "接下来三天有哪些备忘录提醒？"),
    ),
)
def memo_tools():
    from smart_assistant.tools.memo_tool import MemoTool
    from smart_assistant.tools.memo_write_tools import MemoCreateTool
    from smart_assistant.tools.memo_write_tools_v2 import MemoDeleteTool, MemoUpdateTool

    return [
        ToolSpec(
            tool=MemoTool,
            title="查询备忘录",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
        ToolSpec(
            tool=MemoCreateTool,
            title="创建备忘录",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
            confirm=ConfirmPolicy.USER,
        ),
        ToolSpec(
            tool=MemoUpdateTool,
            title="修改备忘录",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
            confirm=ConfirmPolicy.USER,
        ),
        ToolSpec(
            tool=MemoDeleteTool,
            title="删除备忘录",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
            confirm=ConfirmPolicy.USER,
        ),
    ]
