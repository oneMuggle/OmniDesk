from rest_framework import serializers

from .models import RagflowConfig


class RagflowConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = RagflowConfig
        fields = ["id", "name", "api_endpoint", "api_key", "chat_id", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
        # R3-B1: api_key 加密存储,不得在读响应中返回明文密钥;仅允许写入
        # (RagflowConfigViewSet 权限 IsAdminOrReadOnly,任意登录用户可读 —— CRITICAL 同类漏洞)
        extra_kwargs = {"api_key": {"write_only": True}}
