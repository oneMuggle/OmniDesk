from rest_framework import serializers
from .models import KnowledgeBaseDocument, SmartAssistantSession, AgentLog, LlmEndpoint, LlmAppConfig, KnowledgeDataset


class KnowledgeDatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeDataset
        fields = [
            "id",
            "name",
            "description",
            "ragflow_dataset_id",
            "is_active",
            "tags",
            "document_count",
            "priority",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "document_count"]


class KnowledgeBaseDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField(read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    tag_list = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeBaseDocument
        fields = [
            "id",
            "title",
            "file",
            "content_text",
            "category",
            "category_display",
            "tags",
            "tag_list",
            "embedding_status",
            "ragflow_document_id",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "content_text",
            "embedding_status",
            "ragflow_document_id",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]

    def get_tag_list(self, obj):
        if obj.tags:
            return [t.strip() for t in obj.tags.split(",") if t.strip()]
        return []


class SmartAssistantSessionSerializer(serializers.ModelSerializer):
    messages = serializers.JSONField(required=False)

    class Meta:
        model = SmartAssistantSession
        fields = ["id", "title", "messages", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class AgentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentLog
        fields = "__all__"
        read_only_fields = ["created_at"]


class SmartChatRequestSerializer(serializers.Serializer):
    """智能聊天请求"""

    query = serializers.CharField(required=True, help_text="用户问题")
    conversation_id = serializers.IntegerField(required=False, allow_null=True, help_text="可选：关联的会话ID")


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
        fields = [
            "id",
            "name",
            "api_endpoint",
            "is_active",
            "priority",
            "is_fallback",
            "model_capabilities",
            "cost_per_1k_tokens",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {"api_key": {"write_only": True}}


class LlmEndpointCreateSerializer(serializers.ModelSerializer):
    """创建/更新时包含 api_key 和降级相关字段

    api_key 语义:
    - create: 必填(空值在 validate 中拒绝)
    - update: 空/None 表示"保持原值"(前端编辑表单"留空则不修改")
    - 响应不回显 api_key(write_only)
    """

    api_key = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        write_only=True,
        max_length=500,
    )

    class Meta:
        model = LlmEndpoint
        fields = [
            "id",
            "name",
            "api_endpoint",
            "api_key",
            "is_active",
            "priority",
            "is_fallback",
            "model_capabilities",
            "cost_per_1k_tokens",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        if self.instance is None and not (attrs.get("api_key") or "").strip():
            raise serializers.ValidationError({"api_key": ["创建端点时必须提供 API 密钥。"]})
        return attrs

    def update(self, instance, validated_data):
        # 空/空白密钥 → 保持原值;非空才替换
        api_key = validated_data.pop("api_key", None)
        if api_key and str(api_key).strip():
            validated_data["api_key"] = api_key
        return super().update(instance, validated_data)


class LlmAppConfigSerializer(serializers.ModelSerializer):
    endpoint_name = serializers.CharField(source="endpoint.name", read_only=True)
    api_endpoint = serializers.CharField(source="endpoint.api_endpoint", read_only=True)

    class Meta:
        model = LlmAppConfig
        fields = [
            "id",
            "app_name",
            "endpoint",
            "endpoint_name",
            "api_endpoint",
            "model_name",
            "temperature",
            "top_p",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class LlmAppConfigCreateSerializer(serializers.ModelSerializer):
    """创建/更新时的完整字段"""

    class Meta:
        model = LlmAppConfig
        fields = [
            "id",
            "app_name",
            "endpoint",
            "model_name",
            "temperature",
            "top_p",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
