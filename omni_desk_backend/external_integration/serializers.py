from rest_framework import serializers
from .models import ExternalLink, IntegrationService, Plugin, PluginVersion


class ExternalLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalLink
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class IntegrationServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationService
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class PluginVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PluginVersion
        fields = ("id", "version", "file_hash", "manifest", "is_active", "uploaded_by", "uploaded_at", "review_notes")
        read_only_fields = ("id", "uploaded_at")


class PluginSerializer(serializers.ModelSerializer):
    versions = PluginVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Plugin
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class PluginUploadSerializer(serializers.Serializer):
    """插件上传文件序列化器"""

    file = serializers.FileField()
