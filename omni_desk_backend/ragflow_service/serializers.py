from rest_framework import serializers

from .models import RagflowConfig


class RagflowConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = RagflowConfig
        fields = ["id", "name", "api_endpoint", "api_key", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
