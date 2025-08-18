from rest_framework import serializers
from .models import Config, PageConfig

class ConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class PageConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageConfig
        fields = '__all__'
