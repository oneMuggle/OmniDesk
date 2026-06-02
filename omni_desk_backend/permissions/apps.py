import sys

from django.apps import AppConfig
from django.core.management import call_command


class PermissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "permissions"

    def ready(self):
        # Only run this when running the development server
        if "runserver" in sys.argv:
            sys.stdout.write("Running initial route synchronization...\n")
            try:
                call_command("sync_routes")
            except Exception as e:
                sys.stderr.write(f"Error during initial route synchronization: {e}\n")
