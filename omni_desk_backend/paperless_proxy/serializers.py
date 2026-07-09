from rest_framework import serializers
from .models import OutboxItem, DocumentBinding, UserPaperlessBinding, PaperlessHealth


class OutboxItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboxItem
        fields = [
            'id', 'operation', 'status', 'payload', 'binding',
            'retry_count', 'max_retries', 'next_retry_at', 'last_error',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class DocumentBindingSerializer(serializers.ModelSerializer):
    outbox_status = serializers.SerializerMethodField()

    class Meta:
        model = DocumentBinding
        fields = [
            'id', 'source_type', 'source_id', 'paperless_id', 'paperless_checksum',
            'owner', 'title', 'correspondent_id', 'extra_metadata',
            'outbox_status', 'created_at', 'updated_at',
        ]
        read_only_fields = ['paperless_id', 'paperless_checksum', 'created_at', 'updated_at']

    def get_outbox_status(self, obj):
        latest = obj.outbox.order_by('-created_at').first()
        return latest.status if latest else 'synced'


class UserPaperlessBindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPaperlessBinding
        fields = ['id', 'paperless_user_id', 'paperless_username', 'bound_at', 'is_active']
        read_only_fields = fields


class PaperlessHealthSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaperlessHealth
        fields = ['is_healthy', 'last_check_at', 'consecutive_failures', 'last_error']
        read_only_fields = fields