from rest_framework import serializers
from .models import KnowledgeBaseDocument, SmartAssistantSession, AgentLog


class KnowledgeBaseDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = KnowledgeBaseDocument
        fields = ['id', 'title', 'file', 'content_text', 'embedding_status',
                  'ragflow_document_id', 'uploaded_by', 'created_at', 'updated_at']
        read_only_fields = ['content_text', 'embedding_status', 'ragflow_document_id',
                            'uploaded_by', 'created_at', 'updated_at']


class SmartAssistantSessionSerializer(serializers.ModelSerializer):
    messages = serializers.JSONField(required=False)

    class Meta:
        model = SmartAssistantSession
        fields = ['id', 'title', 'messages', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class AgentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentLog
        fields = '__all__'
        read_only_fields = ['created_at']


class SmartChatRequestSerializer(serializers.Serializer):
    """智能聊天请求"""
    query = serializers.CharField(required=True, help_text="用户问题")
    conversation_id = serializers.IntegerField(required=False, allow_null=True,
                                               help_text="可选：关联的会话ID")


class SmartChatResponseSerializer(serializers.Serializer):
    """智能聊天响应"""
    answer = serializers.CharField()
    intent = serializers.CharField()
    tool_used = serializers.CharField(allow_null=True)
    tool_result = serializers.JSONField(allow_null=True)
    sources = serializers.ListField(child=serializers.DictField(), allow_null=True)
