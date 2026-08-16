"""projects serializer 白名单化测试 (R3-B1 PR-4)。

契约(plan §3.2 PR-4):
- ProjectSerializer 白名单 `("id","name","description","start_date","end_date","status","created_at","updated_at")`
- 剔除 `manager` FK(前端未消费)
"""

import pytest

from projects.models import Project
from projects.serializers import ProjectSerializer


@pytest.mark.django_db
class TestProjectSerializerWhitelist:
    def test_fields_whitelisted(self, regular_user_obj):
        project = Project.objects.create(
            name="项目X",
            description="描述",
            status="进行中",
            manager=regular_user_obj,
        )

        data = ProjectSerializer(project).data

        assert set(data.keys()) == {
            "id",
            "name",
            "description",
            "start_date",
            "end_date",
            "status",
            "created_at",
            "updated_at",
        }
        # manager(前端零消费)被剔除
        assert "manager" not in data

    def test_write_accepts_fields(self):
        serializer = ProjectSerializer(
            data={
                "name": "项目Y",
                "description": "描述",
                "status": "进行中",
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["name"] == "项目Y"

    def test_write_accepts_manager(self, regular_user_obj):
        """manager 为 write_only:读响应不含,但写路径接受
        (projects/views.py perform_create: Admin 创建项目必须指定 manager)。"""
        serializer = ProjectSerializer(
            data={
                "name": "项目Z",
                "description": "描述",
                "status": "进行中",
                "manager": regular_user_obj.id,
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert "manager" in serializer.validated_data
