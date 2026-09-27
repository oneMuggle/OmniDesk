"""查看 / 生成 / 校验 AI 能力目录。

用法:
    python manage.py ai_capabilities            # 打印工具集与工具概览
    python manage.py ai_capabilities --json     # 以 JSON 输出（含 MCP ToolAnnotations）
    python manage.py ai_capabilities --write    # 重新生成 docs/technical/46-ai-capability-catalog.md
    python manage.py ai_capabilities --check    # 校验目录与代码一致、权限码存在；不一致时退出码 1
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from smart_assistant.capabilities import capabilities
from smart_assistant.capabilities.catalog import default_catalog_path, render_catalog


class Command(BaseCommand):
    help = "查看、生成或校验 AI 能力目录（docs/technical/46-ai-capability-catalog.md）"

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--write", action="store_true", help="重新生成能力目录文件")
        group.add_argument("--check", action="store_true", help="校验能力目录与代码一致，并检查权限码是否存在")
        group.add_argument("--json", action="store_true", help="以 JSON 输出能力清单")
        parser.add_argument("--path", default=None, help="能力目录文件路径（默认仓库 docs/technical/46-...）")

    def handle(self, *args, **options):
        path = Path(options["path"]) if options["path"] else default_catalog_path()
        content = render_catalog(capabilities)

        if options["write"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"已写入 {path}"))
            return

        if options["check"]:
            problems: list[str] = []
            if not path.exists():
                problems.append(f"能力目录不存在: {path}")
            elif path.read_text(encoding="utf-8") != content:
                problems.append(f"能力目录已过期: {path}")
            problems.extend(f"权限码不存在: {item}" for item in capabilities.missing_permissions())
            if problems:
                for item in problems:
                    self.stderr.write(self.style.ERROR(item))
                raise CommandError("AI 能力目录校验失败，请运行 python manage.py ai_capabilities --write")
            self.stdout.write(self.style.SUCCESS(f"能力目录与代码一致（{len(capabilities.specs())} 个工具）"))
            return

        if options["json"]:
            payload = [
                {
                    "intent": s.intent,
                    "toolset": s.toolset.name,
                    "app_label": s.toolset.app_label,
                    "title": s.spec.title,
                    "risk_level": s.risk_level,
                    "required_permission": s.spec.required_permission,
                    "data_scope": s.spec.data_scope,
                    "confirm": s.spec.confirm,
                    "rollback": s.spec.rollback,
                    "feature_flag": s.spec.feature_flag,
                    "enabled": s.enabled,
                    "version": s.spec.version,
                    "annotations": s.annotations(),
                }
                for s in capabilities.specs()
            ]
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        for toolset in capabilities.toolsets():
            intents = [s.intent for s in capabilities.specs() if s.toolset.name == toolset.name]
            self.stdout.write(f"{toolset.name:<18} {toolset.app_label:<22} {', '.join(intents)}")
        self.stdout.write(f"共 {len(capabilities.toolsets())} 个工具集、{len(capabilities.specs())} 个工具")
