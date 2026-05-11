from rest_framework import serializers
from .models import ExternalLink, IntegrationService


class ExternalLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalLink
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class IntegrationServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationService
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
