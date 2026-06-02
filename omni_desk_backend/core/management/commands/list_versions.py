"""List migration history and version info."""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = "Show current version and migration history summary."

    def handle(self, *args, **options):
        version = getattr(settings, "APP_VERSION", "unknown")
        build_time = getattr(settings, "BUILD_TIME", "unknown")

        self.stdout.write(self.style.SUCCESS(f"Current version: {version}"))
        self.stdout.write(f"Build time: {build_time}")
        self.stdout.write("")

        try:
            recorder = MigrationRecorder(connection)
            applied = recorder.applied_migrations()
        except Exception:
            self.stdout.write(self.style.WARNING("Unable to connect to database. No migration history available."))
            return

        self.stdout.write(f"Applied migrations: {len(applied)}")
        self.stdout.write("")

        # Group by app
        app_migrations = {}
        for app, name in sorted(applied):
            app_migrations.setdefault(app, []).append(name)

        for app in sorted(app_migrations):
            names = app_migrations[app]
            self.stdout.write(f"  {app}: {len(names)} migration(s) applied")
            self.stdout.write(f"    latest -> {names[-1]}")
