"""P1-6 覆盖率补足 + P1 主题:用户管理 API 中 personnel_id 关联行为验证。

参考 user_serializers.py:155-164 与 views.py:166-176,验证:
- partial_update 传入 personnel_id 应自动绑定并同步 real_name
- 不存在的 personnel_id 应返回 404
"""
import pytest
from rest_framework import status

from personnel.models import Personnel


@pytest.mark.django_db
class TestUserAdminPersonnelLink:
    """Admin 通过 PATCH 把 personnel_id 关联到 user。"""

    def test_partial_update_with_personnel_id_binds_and_syncs_real_name(
        self, admin_client, regular_user_obj
    ):
        p = Personnel.objects.create(name="测试人员-001")
        url = f"/api/users/{regular_user_obj.pk}/"
        response = admin_client.patch(
            url,
            {"personnel_id": p.id, "real_name": "should be overridden"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        regular_user_obj.refresh_from_db()
        assert regular_user_obj.personnel_id == p.id
        # real_name 应当被 personnel.name 覆盖
        assert regular_user_obj.real_name == p.name

    def test_partial_update_with_invalid_personnel_id_returns_404(
        self, admin_client, regular_user_obj
    ):
        url = f"/api/users/{regular_user_obj.pk}/"
        response = admin_client.patch(
            url,
            {"personnel_id": 99999},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
