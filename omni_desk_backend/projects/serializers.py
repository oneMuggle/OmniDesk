from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        # R3-B1: 白名单化。manager 读响应收敛(前端零消费),写路径保留
        # (projects/views.py perform_create: Admin 创建时可经请求体指定 manager;
        #  Manager 路径由 perform_create 注入,故 manager 不可设 required)
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
