from django.apps import AppConfig


class SmartAssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "smart_assistant"
    verbose_name = "智能助手"

    def ready(self):
        """注册所有工具"""
        from .tools.registry import ToolRegistry
        from .tools.schedule_tool import ScheduleTool
        from .tools.personnel_tool import PersonnelTool
        from .tools.rag_tool import RAGTool
        from .tools.document_tool import DocumentTool
        from .tools.event_tool import EventTool
        from .tools.memo_tool import MemoTool
        from .tools.project_tool import ProjectTool
        from .tools.news_tool import NewsTool
        from .tools.meeting_room_tool import MeetingRoomTool
        from .tools.sensor_tool import SensorTool
        from .tools.announcement_tool import AnnouncementTool
        from .tools.compliance_tool import ComplianceTool

        ToolRegistry.register(ScheduleTool())
        ToolRegistry.register(PersonnelTool())
        ToolRegistry.register(RAGTool())
        ToolRegistry.register(DocumentTool())
        ToolRegistry.register(EventTool())
        ToolRegistry.register(MemoTool())
        ToolRegistry.register(ProjectTool())
        ToolRegistry.register(NewsTool())
        ToolRegistry.register(MeetingRoomTool())
        ToolRegistry.register(SensorTool())
        ToolRegistry.register(AnnouncementTool())
        ToolRegistry.register(ComplianceTool())
