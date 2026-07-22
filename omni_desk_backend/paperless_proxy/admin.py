"""paperless_proxy Django admin 注册"""

from django.contrib import admin

from .models import DocumentBinding, OutboxItem, PaperlessHealth, UserPaperlessBinding


@admin.register(DocumentBinding)
class DocumentBindingAdmin(admin.ModelAdmin):
    list_display = ("__str__", "owner", "paperless_id", "source_type", "created_at")
    list_filter = ("source_type",)
    search_fields = ("title", "source_id")
    raw_id_fields = ("owner",)
    readonly_fields = ("paperless_checksum", "created_at", "updated_at")


@admin.register(OutboxItem)
class OutboxItemAdmin(admin.ModelAdmin):
    list_display = ("id", "operation", "status", "binding", "retry_count", "next_retry_at", "created_at")
    list_filter = ("operation", "status")
    search_fields = ("binding__title",)
    raw_id_fields = ("binding", "created_by")
    readonly_fields = ("payload", "last_error", "created_at", "updated_at")


@admin.register(UserPaperlessBinding)
class UserPaperlessBindingAdmin(admin.ModelAdmin):
    list_display = ("user", "paperless_username", "is_active", "bound_at")
    search_fields = ("user__username", "paperless_username")
    raw_id_fields = ("user",)


@admin.register(PaperlessHealth)
class PaperlessHealthAdmin(admin.ModelAdmin):
    list_display = ("is_healthy", "consecutive_failures", "last_check_at")
    readonly_fields = ("last_check_at",)
