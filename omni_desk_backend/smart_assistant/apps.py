from django.apps import AppConfig


class SmartAssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'smart_assistant'
    verbose_name = '智能助手'

    def ready(self):
        """注册所有工具"""
        from .tools.registry import ToolRegistry
        from .tools.schedule_tool import ScheduleTool
        from .tools.personnel_tool import PersonnelTool
        from .tools.rag_tool import RAGTool

        ToolRegistry.register(ScheduleTool())
        ToolRegistry.register(PersonnelTool())
        ToolRegistry.register(RAGTool())
