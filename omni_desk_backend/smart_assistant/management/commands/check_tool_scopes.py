"""校验所有 smart_assistant 工具实现 scope 过滤。

用法:python manage.py check_tool_scopes
退出码:0 = 通过;1 = 有工具未实现必填方法

CI 步骤:.github/workflows/ci.yml 在 backend pytest 前运行此命令。
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from smart_assistant.tools.registry import ToolRegistry


class Command(BaseCommand):
    help = "校验所有工具实现 build_base_queryset + _scope_self(scope 权限模型)"

    REQUIRED_METHODS = ("build_base_queryset", "_scope_self")

    def handle(self, *args, **options):
        tools = ToolRegistry._tools
        total = len(tools)
        failures = []

        self.stdout.write(f"检查 {total} 个工具的 scope 实现...\n")

        for intent_type, tool in tools.items():
            for method in self.REQUIRED_METHODS:
                if not hasattr(tool, method):
                    failures.append(
                        {
                            "intent_type": intent_type,
                            "tool_class": tool.__class__.__name__,
                            "missing": method,
                        }
                    )

        if failures:
            self.stdout.write(self.style.ERROR(f"\n❌ {len(failures)} 个工具缺方法:\n"))
            for f in failures:
                self.stdout.write(
                    self.style.ERROR(f"  - {f['tool_class']} (intent={f['intent_type']}) 缺 {f['missing']}\n")
                )
            self.stdout.write(
                self.style.ERROR("\n修复:每个 BaseTool 子类必须实现 build_base_queryset() 和 _scope_self()\n")
            )
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(f"✅ 全部 {total} 个工具实现 build_base_queryset + _scope_self\n"))
