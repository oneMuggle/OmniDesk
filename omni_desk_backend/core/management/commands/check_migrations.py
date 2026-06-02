"""Check pending migrations and detect destructive changes."""

import re
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection, migrations as django_migrations
from django.db.migrations.loader import MigrationLoader


DESTRUCTIVE_PATTERNS = [
    re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE),
    re.compile(r"\bALTER\s+TABLE\b.*\bDROP\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
]


class Command(BaseCommand):
    help = "Check pending migrations and warn about destructive changes."

    def handle(self, *args, **options):
        loader = MigrationLoader(connection)
        loader.build_graph()

        # Find pending migrations
        pending = []
        for app_config in apps.get_app_configs():
            app_label = app_config.label
            # Skip third-party apps without migrations module
            if not hasattr(app_config, "migrations"):
                continue
            graph = loader.graph
            for migration in app_config.migrations:
                key = (app_label, migration.name.replace(".py", ""))
                applied = key in loader.applied_migrations
                if not applied and not migration.name.startswith("__"):
                    pending.append((app_label, migration, key))

        if not pending:
            self.stdout.write(self.style.SUCCESS("No pending migrations found."))
            return

        self.stdout.write(self.style.WARNING(f"Found {len(pending)} pending migration(s):"))
        self.stdout.write("")

        destructive_found = False
        for app_label, migration, key in pending:
            prefix = "  "
            label = f"[{app_label}] {migration.name}"

            # Check migration operations for destructive actions
            ops_desc = []
            for op in migration.operations:
                op_str = str(type(op).__name__)
                if isinstance(op, django_migrations.DeleteModel):
                    ops_desc.append(f"DELETE MODEL: {op.name}")
                    destructive_found = True
                elif isinstance(op, django_migrations.RemoveField):
                    ops_desc.append(f"REMOVE FIELD: {op.model_name}.{op.name}")
                    destructive_found = True
                elif isinstance(op, django_migrations.AlterField):
                    ops_desc.append(f"ALTER FIELD: {op.model_name}.{op.name}")
                elif isinstance(op, django_migrations.AddField):
                    ops_desc.append(f"ADD FIELD: {op.model_name}.{op.name}")
                elif isinstance(op, django_migrations.CreateModel):
                    ops_desc.append(f"CREATE MODEL: {op.name}")
                else:
                    ops_desc.append(op_str)

            self.stdout.write(f"{prefix}{label}")
            for desc in ops_desc:
                self.stdout.write(f"{prefix}    -> {desc}")
            self.stdout.write("")

        if destructive_found:
            self.stdout.write(
                self.style.ERROR(
                    "WARNING: Destructive changes detected (DROP TABLE, DROP COLUMN, etc.).\n"
                    "This may result in data loss. Review carefully before proceeding."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("No destructive changes detected."))
