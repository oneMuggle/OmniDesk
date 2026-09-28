from django.apps import AppConfig
from django.conf import settings


class SmartAssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "smart_assistant"
    verbose_name = "智能助手"

    def ready(self):
        """自动发现并注册各 app 的 AI 工具,然后在 DEBUG 模式下校验每个工具已实现 scope 方法。"""
        # R5-B4: LLMRouter 配置缓存失效信号(LlmAppConfig/LlmEndpoint 变更时)
        from llm_service import signals as llm_signals  # noqa: F401

        # 工具注册:各 app 的 ai_tools.py 声明工具集,此处自动发现 + 启动自检
        # (声明错误直接抛 ImproperlyConfigured,启动失败)。必须在 scope 校验之前完成。
        # 规则与字段见 smart_assistant/capabilities 与 docs/technical/46-ai-capability-catalog.md。
        from .capabilities import capabilities

        capabilities.discover()

        # 钩子注册:PII 脱敏(POST_EXECUTE)+ 超时熔断恢复(ON_FAILURE)挂到
        # 全局 HookRegistry。接线方式与 AuditLogHook 文档约定一致
        # (registry.register + HookEvent);区别在于审计钩子按任务实例化,
        # 而这两个是无状态全局钩子,启动时一次性注册。
        # 调用点:orchestrator 单工具执行 / ToolChainExecutor 逐步执行经
        # hooks.wiring 的同步入口(execute_guarded / apply_post_execute_hooks)
        # 触发;register_builtin_hooks 幂等,ready() 多次执行不会重复挂载。
        from .hooks.wiring import register_builtin_hooks

        register_builtin_hooks()

        # S4-2:公告 / 文档库变更 → 自动入库同步(未配置入库数据集时信号内直接返回)
        from .knowledge import signals as knowledge_signals

        knowledge_signals.connect()

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
