from django.urls import path
from core.api import version_info, changelog, migration_status

urlpatterns = [
    path('system/version/', version_info, name='version-info'),
    path('system/changelog/', changelog, name='changelog'),
    path('system/migrations/', migration_status, name='migration-status'),
]
