from django.apps import AppConfig
from django.conf import settings


class SmartAssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "smart_assistant"
    verbose_name = "智能助手"

    def ready(self):
        """注册所有工具,然后在 DEBUG 模式下校验每个工具已实现 scope 方法。"""
        # R5-B4: LLMRouter 配置缓存失效信号(LlmAppConfig/LlmEndpoint 变更时)
        from llm_service import signals as llm_signals  # noqa: F401

        # 工具注册(原逻辑保留,必须在校验之前完成)
        from .tools.registry import ToolRegistry
        from .tools.schedule_tool import ScheduleTool
        from .tools.personnel_tool import PersonnelTool
        from .tools.rag_tool import RAGTool
        from .tools.document_tool import DocumentTool
        from .tools.event_tool import EventTool
        from .tools.memo_tool import MemoTool
        from .tools.memo_write_tools import MemoCreateTool
        from .tools.memo_write_tools_v2 import MemoUpdateTool, MemoDeleteTool
        from .tools.project_tool import ProjectTool
        from .tools.news_tool import NewsTool
        from .tools.meeting_room_tool import MeetingRoomTool
        from .tools.sensor_tool import SensorTool
        from .tools.announcement_tool import AnnouncementTool
        from .tools.compliance_tool import ComplianceTool
        from .tools.external_link_tool import ExternalLinkTool
        from .tools.swap_request_tool import (
            SwapRequestQueryTool,
            SwapRequestCreateTool,
            SwapRequestDecideTool,
        )
        from .tools.office_read_tool import OfficeReadTool
        from .tools.office_generate_tool import OfficeGenerateTool
        from .tools.spreadsheet_tool import SpreadsheetTool
        from .tools.notify_tool import NotifyTool

        ToolRegistry.register(ScheduleTool())
        ToolRegistry.register(PersonnelTool())
        ToolRegistry.register(RAGTool())
        ToolRegistry.register(DocumentTool())
        ToolRegistry.register(EventTool())
        ToolRegistry.register(MemoTool())
        ToolRegistry.register(MemoCreateTool())
        ToolRegistry.register(MemoUpdateTool())
        ToolRegistry.register(MemoDeleteTool())
        ToolRegistry.register(ProjectTool())
        ToolRegistry.register(NewsTool())
        ToolRegistry.register(MeetingRoomTool())
        ToolRegistry.register(SensorTool())
        ToolRegistry.register(AnnouncementTool())
        ToolRegistry.register(ComplianceTool())
        ToolRegistry.register(ExternalLinkTool())
        ToolRegistry.register(SwapRequestQueryTool())
        ToolRegistry.register(SwapRequestCreateTool())
        ToolRegistry.register(SwapRequestDecideTool())
        ToolRegistry.register(OfficeReadTool())
        ToolRegistry.register(OfficeGenerateTool())
        ToolRegistry.register(SpreadsheetTool())
        ToolRegistry.register(NotifyTool())

        # 钩子注册:PII 脱敏(POST_EXECUTE)+ 超时熔断恢复(ON_FAILURE)挂到
        # 全局 HookRegistry。接线方式与 AuditLogHook 文档约定一致
        # (registry.register + HookEvent);区别在于审计钩子按任务实例化,
        # 而这两个是无状态全局钩子,启动时一次性注册。
        # 调用点:orchestrator 单工具执行 / ToolChainExecutor 逐步执行经
        # hooks.wiring 的同步入口(execute_guarded / apply_post_execute_hooks)
        # 触发;register_builtin_hooks 幂等,ready() 多次执行不会重复挂载。
        from .hooks.wiring import register_builtin_hooks

        register_builtin_hooks()

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
