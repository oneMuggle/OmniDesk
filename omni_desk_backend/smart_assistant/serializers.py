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


class SessionForkSerializer(serializers.Serializer):
    """会话复制（fork）请求参数

    契约（字段均可选）：
        - at_message: 非负整数，仅复制前 N 条消息；缺省 / null 表示全量复制
        - title: 新会话标题（≤255 字符）；缺省 / 空串时使用「原标题（副本）」
    """

    at_message = serializers.IntegerField(
        min_value=0,
        required=False,
        allow_null=True,
        help_text="仅复制前 N 条消息，缺省全量复制",
    )
    title = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="新会话标题，缺省为「原标题（副本）」",
    )


class AgentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentLog
        fields = [
            "id",
            "user_query",
            "intent",
            "tool_used",
            "tool_input",
            "tool_output",
            "llm_response",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class AgentLogFeedbackSerializer(serializers.Serializer):
    """Agent 日志用户反馈请求（赞/踩）

    契约：{"feedback": "up" | "down" | null}
        - "up" / "down"：写入 AgentLog.user_feedback（允许改选覆盖）
        - null：清除已有反馈
        - 其他值 / 缺省：校验失败（400）
    """

    feedback = serializers.ChoiceField(
        choices=["up", "down"],
        allow_null=True,
        help_text="用户反馈：up=赞，down=踩，null=清除",
    )


class SmartChatRequestSerializer(serializers.Serializer):
    """智能聊天请求（支持附件上传）"""

    query = serializers.CharField(required=True, help_text="用户问题")
    conversation_id = serializers.IntegerField(required=False, allow_null=True, help_text="可选：关联的会话ID")
    confirm_token = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="可选:二次确认 token,带此字段走 replay 路径(跳过 orchestrator 拦截,直接执行工具)",
    )
    attachment = serializers.FileField(
        required=False, allow_null=True, help_text="可选：Office 附件（docx/pdf/xlsx/pptx/txt/md/csv，≤10MB）"
    )


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
    """创建/更新时包含 api_key 和降级相关字段"""

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
