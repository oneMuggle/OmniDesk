from rest_framework import serializers
from django.contrib.auth.models import Group
from .models import Page, PageVisibility, OllamaConfig


class GroupSerializer(serializers.ModelSerializer):
    """
    序列化 Django 内置的 Group 模型。
    """
    class Meta:
        model = Group
        fields = ('id', 'name')


class PageSerializer(serializers.ModelSerializer):
    """
    序列化 Page 模型。
    """
    class Meta:
        model = Page
        fields = '__all__'


class PageVisibilitySerializer(serializers.ModelSerializer):
    """
    序列化 PageVisibility 模型，并提供 page 和 group 的嵌套表示。
    """
    page = PageSerializer(read_only=True)
    group = GroupSerializer(read_only=True)

    class Meta:
        model = PageVisibility
        fields = '__all__'

class OllamaConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = OllamaConfig
        fields = ['id', 'alias', 'api_endpoint', 'model', 'temperature', 'top_p', 'is_default', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
