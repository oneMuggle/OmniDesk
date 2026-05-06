from django.contrib.auth.models import Group
from rest_framework import serializers

from .models import PageRoute


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name']

class PageRouteSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = PageRoute
        fields = ['id', 'name', 'path', 'component', 'parent', 'children']

    def get_children(self, obj):
        children = PageRoute.objects.filter(parent=obj)
        if children.exists():
            return PageRouteSerializer(children, many=True).data
        return []
