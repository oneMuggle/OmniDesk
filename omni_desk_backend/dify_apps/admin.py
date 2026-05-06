from django.contrib import admin

# Register your models here.
from .models import DifyApp


@admin.register(DifyApp)
class DifyAppAdmin(admin.ModelAdmin):
    list_display = ('name', 'embed_url', 'is_active', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    list_filter = ('is_active',)
    date_hierarchy = 'created_at'
