"""Check pending migrations and detect destructive changes.

基于 Django MigrationLoader.graph 真实枚举所有 app 迁移(包括第三方 app 与无
migrations 模块属性的 app),识别 DeleteModel / RemoveField / RemoveConstraint
三类 destructive 操作。

提供 --fail-on-destructive 选项:检测到 destructive 时 sys.exit(2),用于升级
脚本中作为硬门禁。默认行为仅打印警告(向后兼容)。
"""

import sys

from django.db import connection, migrations as django_migrations
from django.core.management.base import BaseCommand
from django.db.migrations.loader import MigrationLoader


class Command(BaseCommand):
    help = "Check pending migrations and warn about destructive changes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-on-destructive",
            action="store_true",
            help="Exit with code 2 when destructive migrations (DeleteModel / "
            "RemoveField / RemoveConstraint) are detected. Without this flag, "
            "the command only warns and exits 0.",
        )

    def handle(self, *args, **options):
        loader = MigrationLoader(connection)
        loader.build_graph()

        pending = self._collect_pending(loader)
        if not pending:
            self.stdout.write(self.style.SUCCESS("No pending migrations found."))
            return

        self.stdout.write(self.style.WARNING(f"Found {len(pending)} pending migration(s):"))
        self.stdout.write("")

        destructive_found = False
        for app_label, migration_name, migration in pending:
            label = f"[{app_label}] {migration_name}"
            self.stdout.write(f"  {label}")

            for op in migration.operations:
                desc, is_destructive = self._describe_operation(op)
                if is_destructive:
                    destructive_found = True
                self.stdout.write(f"      -> {desc}")
            self.stdout.write("")

        if destructive_found:
            self.stdout.write(
                self.style.ERROR(
                    "WARNING: Destructive changes detected "
                    "(DeleteModel / RemoveField / RemoveConstraint). "
                    "This may result in data loss. Review carefully before proceeding."
                )
            )
            if options.get("fail_on_destructive"):
                sys.exit(2)
        else:
            self.stdout.write(self.style.SUCCESS("No destructive changes detected."))

    # ─── helpers ──────────────────────────────────────────────
    def _collect_pending(self, loader):
        """从 loader.graph.nodes 中收集 pending 迁移。

        显式走 loader.graph 而非 apps.get_app_configs() + app_config.migrations,
        保证能枚举所有 app(包括第三方 app 与无 migrations 模块属性的 app)。
        """
        pending = []
        for node_key, migration in loader.graph.nodes.items():
            app_label, migration_name = node_key
            if node_key in loader.applied_migrations:
                continue
            # 跳过包标记(如 __init__.py)
            if migration.name.startswith("__"):
                continue
            pending.append((app_label, migration_name, migration))
        return pending

    def _describe_operation(self, op):
        """返回 (description, is_destructive) 元组。"""
        if isinstance(op, django_migrations.DeleteModel):
            return (f"DELETE MODEL: {op.name}", True)
        if isinstance(op, django_migrations.RemoveField):
            return (f"REMOVE FIELD: {op.model_name}.{op.name}", True)
        if isinstance(op, django_migrations.RemoveConstraint):
            return (
                f"REMOVE CONSTRAINT: {op.model_name}.{op.name}"
                if hasattr(op, "name")
                else f"REMOVE CONSTRAINT: {op.model_name}",
                True,
            )
        if isinstance(op, django_migrations.AlterField):
            return (f"ALTER FIELD: {op.model_name}.{op.name}", False)
        if isinstance(op, django_migrations.AddField):
            return (f"ADD FIELD: {op.model_name}.{op.name}", False)
        if isinstance(op, django_migrations.CreateModel):
            return (f"CREATE MODEL: {op.name}", False)
        return (type(op).__name__, False)
