from django.apps import AppConfig
from django.conf import settings


class SmartAssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "smart_assistant"
    verbose_name = "智能助手"

    def ready(self):
        """注册所有工具,然后在 DEBUG 模式下校验每个工具已实现 scope 方法。"""
        # 工具注册(原逻辑保留,必须在校验之前完成)
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
        from .tools.external_link_tool import ExternalLinkTool

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
        ToolRegistry.register(ExternalLinkTool())

        # 仅在 DEBUG 模式下启动时校验 scope(避免生产启动变慢)。
        # 注:必须在工具注册之后,否则 check_tool_scopes 看到的是空 registry。
        if getattr(settings, "DEBUG", False):
            try:
                from django.core.management import call_command

                call_command("check_tool_scopes", verbosity=0)
            except SystemExit as e:
                if e.code != 0:
                    import sys

                    sys.stderr.write("[smart_assistant] check_tool_scopes failed at startup\n")
                    # 不阻止启动(仅警告),CI 会真正 fail
