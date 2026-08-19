"""projects serializer 白名单化测试 (R3-B1 PR-4)。

契约(plan §3.2 PR-4):
- ProjectSerializer 白名单 `("id","name","description","start_date","end_date","status","manager","created_at","updated_at")`
- `manager` 为 write_only:读响应收敛(前端零消费),写路径保留
  (projects/views.py perform_create: Admin 创建项目时经请求体指定 manager)
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
        # manager 为 write_only,读响应不含(前端零消费)
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
        (projects/views.py perform_create: Admin 创建项目时必须指定 manager)。"""
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

    def test_update_without_manager_keeps_existing_manager(self, regular_user_obj):
        """PATCH/PUT 更新不带 manager 时,已存在的 manager 不被静默清除
        (防未来把 manager 误设 read_only/required 导致数据丢失)。"""
        project = Project.objects.create(
            name="项目A",
            description="描述",
            status="进行中",
            manager=regular_user_obj,
        )

        serializer = ProjectSerializer(
            instance=project,
            data={"name": "项目A-改名"},
            partial=True,
        )

        assert serializer.is_valid(), serializer.errors
        serializer.save()
        project.refresh_from_db()
        assert project.name == "项目A-改名"
        assert project.manager == regular_user_obj
