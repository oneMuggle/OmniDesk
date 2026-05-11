from django.contrib import admin
from .models import ExternalLink, IntegrationService, Plugin, PluginVersion, PluginCallLog


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


class PluginVersionInline(admin.TabularInline):
    model = PluginVersion
    extra = 0
    readonly_fields = ('uploaded_at', 'file_hash')


@admin.register(Plugin)
class PluginAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'category', 'status', 'interface_version', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [PluginVersionInline]


@admin.register(PluginVersion)
class PluginVersionAdmin(admin.ModelAdmin):
    list_display = ('plugin', 'version', 'is_active', 'uploaded_at', 'file_hash')
    list_filter = ('is_active',)
    readonly_fields = ('uploaded_at', 'file_hash')


@admin.register(PluginCallLog)
class PluginCallLogAdmin(admin.ModelAdmin):
    list_display = ('plugin_version', 'user', 'status', 'execution_time_ms', 'created_at')
    list_filter = ('status',)
    readonly_fields = ('created_at',)
