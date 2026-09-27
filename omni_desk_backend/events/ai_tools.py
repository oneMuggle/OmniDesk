"""排班、日程与换班的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import (
    LOGIN_ONLY,
    ROLLBACK_AGENT_WRITE_LOG,
    ConfirmPolicy,
    DataScope,
    QuickPrompt,
    ToolSpec,
    toolset,
)


@toolset(
    "schedule",
    title="排班与日程",
    routes=(r"^/schedule", r"^/shift-schedule", r"^/trial-schedule", r"^/events", r"^/control-panel/schedule"),
    quick_prompts=(
        QuickPrompt("今天安排", "我今天有什么安排？", routes=(r"^/$",)),
        QuickPrompt("明天谁值班", "明天谁值班？"),
        QuickPrompt("本周节假日", "这周有哪些节假日或调休？"),
        QuickPrompt("换班申请", "我收到的换班申请有哪些？"),
    ),
)
def schedule_tools():
    from smart_assistant.tools.schedule_tool import ScheduleTool
    from smart_assistant.tools.event_tool import EventTool
    from smart_assistant.tools.swap_request_tool import (
        SwapRequestCreateTool,
        SwapRequestDecideTool,
        SwapRequestQueryTool,
    )
    from smart_assistant.tools.trial_write_tools import TrialCreateTool

    return [
        ToolSpec(
            tool=ScheduleTool,
            title="查询排班",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
        ToolSpec(
            tool=EventTool,
            title="查询日程与节假日",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
        ToolSpec(
            tool=SwapRequestQueryTool,
            title="查询换班申请",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
        ToolSpec(
            tool=SwapRequestCreateTool,
            title="发起换班申请",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
            confirm=ConfirmPolicy.USER,
        ),
        ToolSpec(
            tool=SwapRequestDecideTool,
            title="处理换班申请",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
            confirm=ConfirmPolicy.USER,
        ),
        ToolSpec(
            tool=TrialCreateTool,
            title="创建试验日程",
            # 与试验接口一致：管理员 / HR（工具内 is_privileged_user 校验）；时段冲突只提示不拦截
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.MODULE,
            confirm=ConfirmPolicy.USER,
            rollback=ROLLBACK_AGENT_WRITE_LOG,
        ),
    ]
