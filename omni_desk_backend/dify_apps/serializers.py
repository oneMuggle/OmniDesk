from rest_framework import serializers
from .models import DifyApp

class DifyAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = DifyApp
        fields = ['id', 'name', 'description', 'embed_url', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'is_active': {'required': False}
        }