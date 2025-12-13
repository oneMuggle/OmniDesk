from django.apps import AppConfig
import sys
from django.core.management import call_command


class PermissionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'omni_desk_backend.permissions'

    def ready(self):
        # Only run this when running the development server
        if 'runserver' in sys.argv:
            self.stdout.write("Running initial route synchronization...")
            try:
                call_command('sync_routes')
            except Exception as e:
                self.stderr.write(f"Error during initial route synchronization: {e}")
