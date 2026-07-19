"""Django 管理命令 — 一次性规范化 CHANGELOG.md 历史 header.

处理:
  - '## [vX.Y.Z]' → '## [X.Y.Z]'  (去除 v 前缀)
  - '## [X.Y.Z 中文]' → '## [X.Y.Z]'  (去除中文/空格后缀)
  - '## [渠道机制引入]' 这类非版本标题行原样保留(显式跳过)

典型用法:
  python manage.py normalize_changelog_headers --dry-run   # 预演
  python manage.py normalize_changelog_headers             # 实际执行
"""

import re

from django.core.management.base import BaseCommand

from core.version_utils import normalize_changelog_header


class Command(BaseCommand):
    help = "一次性规范化 CHANGELOG.md 历史 header: 去掉 v 前缀 / 跳过非版本标题"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="仅打印变更,不写文件",
        )

    def handle(self, *args, **options):
        # 在运行时 lookup CHANGELOG_FILE,这样测试 monkeypatch generate_release.CHANGELOG_FILE 才能生效
        from core.management.commands.generate_release import CHANGELOG_FILE

        content = CHANGELOG_FILE.read_text()
        pattern = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)
        changes: list[tuple[str, str]] = []
        skipped: list[str] = []

        def replace(match: "re.Match[str]") -> str:
            raw = match.group(1)
            if raw == "未发布":
                return match.group(0)
            normalized = normalize_changelog_header(raw)
            if normalized is None:
                skipped.append(raw)
                return match.group(0)
            if normalized != raw:
                changes.append((raw, normalized))
            return f"## [{normalized}]"

        new_content = pattern.sub(replace, content)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("=== DRY RUN (未修改文件) ==="))
        else:
            CHANGELOG_FILE.write_text(new_content)

        self.stdout.write(f"已规范化 {len(changes)} 个 header:")
        for old, new in changes:
            self.stdout.write(f"  - [{old}] → [{new}]")
        self.stdout.write(f"跳过 {len(skipped)} 个非版本标题:")
        for s in skipped:
            self.stdout.write(f"  - [{s}]")
