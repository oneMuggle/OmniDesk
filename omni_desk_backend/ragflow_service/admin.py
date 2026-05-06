from django.contrib import admin

from .models import RagflowConfig


@admin.register(RagflowConfig)
class RagflowConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'api_endpoint', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'api_endpoint')
    list_editable = ('is_active',)
