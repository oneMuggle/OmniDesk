from django.contrib import admin
from .models import ExternalLink, IntegrationService


@admin.register(ExternalLink)
class ExternalLinkAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'url', 'is_active', 'sort_order', 'created_at')
    list_filter = ('category', 'is_active', 'sso_enabled')
    search_fields = ('name', 'url', 'description')
    ordering = ('category', 'sort_order')
    list_editable = ('sort_order', 'is_active')


@admin.register(IntegrationService)
class IntegrationServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'integration_type', 'endpoint_url', 'is_active', 'created_at')
    list_filter = ('integration_type', 'is_active')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
