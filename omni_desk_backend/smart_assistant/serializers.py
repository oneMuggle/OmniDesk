from rest_framework import serializers
from .models import KnowledgeBaseDocument, SmartAssistantSession, AgentLog, LlmEndpoint, LlmAppConfig


class KnowledgeBaseDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField(read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    tag_list = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeBaseDocument
        fields = ['id', 'title', 'file', 'content_text', 'category', 'category_display',
                  'tags', 'tag_list', 'embedding_status',
                  'ragflow_document_id', 'uploaded_by', 'created_at', 'updated_at']
        read_only_fields = ['content_text', 'embedding_status', 'ragflow_document_id',
                            'uploaded_by', 'created_at', 'updated_at']

    def get_tag_list(self, obj):
        if obj.tags:
            return [t.strip() for t in obj.tags.split(',') if t.strip()]
        return []


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


class LlmEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = LlmEndpoint
        fields = ['id', 'name', 'api_endpoint', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {'api_key': {'write_only': True}}


class LlmEndpointCreateSerializer(serializers.ModelSerializer):
    """创建/更新时包含 api_key"""
    class Meta:
        model = LlmEndpoint
        fields = ['id', 'name', 'api_endpoint', 'api_key', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class LlmAppConfigSerializer(serializers.ModelSerializer):
    endpoint_name = serializers.CharField(source='endpoint.name', read_only=True)
    api_endpoint = serializers.CharField(source='endpoint.api_endpoint', read_only=True)

    class Meta:
        model = LlmAppConfig
        fields = ['id', 'app_name', 'endpoint', 'endpoint_name', 'api_endpoint',
                  'model_name', 'temperature', 'top_p', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class LlmAppConfigCreateSerializer(serializers.ModelSerializer):
    """创建/更新时的完整字段"""
    class Meta:
        model = LlmAppConfig
        fields = ['id', 'app_name', 'endpoint', 'model_name', 'temperature',
                  'top_p', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
