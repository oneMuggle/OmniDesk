"""会议室模块的 AI 工具声明。

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
    "meeting_rooms",
    title="会议室",
    routes=(r"^/meeting-rooms", r"^/control-panel/meeting-rooms"),
    quick_prompts=(
        QuickPrompt("空闲会议室", "今天下午有哪些空闲的会议室？"),
        QuickPrompt("我的预约", "我这周预约了哪些会议室？", routes=(r"^/$", r"^/meeting-rooms")),
    ),
)
def meeting_room_tools():
    from smart_assistant.tools.meeting_room_tool import MeetingRoomTool
    from smart_assistant.tools.meeting_room_write_tools import MeetingRoomBookTool, MeetingRoomCancelTool

    return [
        ToolSpec(
            tool=MeetingRoomTool,
            title="查询会议室",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
        ToolSpec(
            tool=MeetingRoomBookTool,
            title="预约会议室",
            # 与页面一致：所有登录用户可预约；冲突检查沿用模型 clean()
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.MODULE,
            confirm=ConfirmPolicy.USER,
            rollback=ROLLBACK_AGENT_WRITE_LOG,
        ),
        ToolSpec(
            tool=MeetingRoomCancelTool,
            title="取消会议室预约",
            # AI 只能取消本人、未开始的预约（即使是管理员）
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.OWNER,
            confirm=ConfirmPolicy.USER,
            rollback=ROLLBACK_AGENT_WRITE_LOG,
        ),
    ]
