from django.contrib import admin
from .models import KnowledgeBaseDocument, SmartAssistantSession, AgentLog


@admin.register(KnowledgeBaseDocument)
class KnowledgeBaseDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'embedding_status', 'uploaded_by', 'created_at')
    list_filter = ('embedding_status',)
    search_fields = ('title',)


@admin.register(SmartAssistantSession)
class SmartAssistantSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at')
    list_filter = ('created_at',)


@admin.register(AgentLog)
class AgentLogAdmin(admin.ModelAdmin):
    list_display = ('user_query', 'intent', 'tool_used', 'created_at')
    list_filter = ('intent', 'tool_used', 'created_at')
    search_fields = ('user_query',)
