"""会议室模块的 AI 工具声明。

由 ``smart_assistant.capabilities`` 在启动时自动发现，见 ``docs/technical/46-ai-capability-catalog.md``。
"""

from smart_assistant.capabilities import DataScope, LOGIN_ONLY, ToolSpec, toolset, QuickPrompt


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

    return [
        ToolSpec(
            tool=MeetingRoomTool,
            title="查询会议室",
            required_permission=LOGIN_ONLY,
            data_scope=DataScope.SCOPE,
        ),
    ]
