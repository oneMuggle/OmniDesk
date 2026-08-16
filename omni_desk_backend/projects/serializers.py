from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        # R3-B1: 白名单化。manager 读响应收敛(前端零消费),但保留写能力
        # (projects/views.py perform_create: Admin 创建时必须指定 manager)
        fields = [
            "id",
            "name",
            "description",
            "start_date",
            "end_date",
            "status",
            "manager",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "manager": {"write_only": True},
        }
