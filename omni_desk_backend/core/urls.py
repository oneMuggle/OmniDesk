from django.urls import path
from core.api import version_info, changelog, migration_status

urlpatterns = [
    path("version/", version_info, name="version-info"),
    path("changelog/", changelog, name="changelog"),
    path("migrations/", migration_status, name="migration-status"),
]
