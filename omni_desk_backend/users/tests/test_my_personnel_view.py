"""P2-3 MyPersonnelView — 集成测试

端点:GET / PATCH /api/users/me/personnel/
- GET:返回当前用户关联的 Personnel(PersonnelSelfSerializer)
- PATCH:仅允许改白名单字段(date_of_birth / phone_number / address)
- L2 防护:perform_update 再次过滤,即使客户端绕过 L1 也无法写入
- 无关联 Personnel → 404
- 触发"信息更新"通知
"""
import pytest
from rest_framework import status

from notifications.models import Notification
from personnel.models import Personnel


URL = "/api/users/me/personnel/"


def _link(regular_user_obj, **kwargs):
    """helper:创建一个 Personnel 并关联到 regular_user_obj。
    name 字段强制使用 regular_user_obj.username(忽略 kwargs 中的 name)。"""
    p = Personnel.objects.create(
        name=regular_user_obj.username,
        **{k: v for k, v in kwargs.items() if k != "name"},
    )
    regular_user_obj.personnel = p
    regular_user_obj.save()
    return p


@pytest.mark.django_db
class TestMyPersonnelGet:
    """GET /api/users/me/personnel/"""

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_without_personnel_returns_404(self, regular_client):
        response = regular_client.get(URL)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_user_with_personnel_returns_200(self, regular_client, regular_user_obj):
        _link(regular_user_obj, phone_number="13800000000")
        response = regular_client.get(URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == regular_user_obj.username
        assert response.data["phone_number"] == "13800000000"


@pytest.mark.django_db
class TestMyPersonnelPatchAllowedFields:
    """PATCH 白名单字段应成功。"""

    def test_update_phone_number_succeeds(self, regular_client, regular_user_obj):
        _link(regular_user_obj, phone_number="13800000000")
        response = regular_client.patch(
            URL, {"phone_number": "13911111111"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        regular_user_obj.personnel.refresh_from_db()
        assert regular_user_obj.personnel.phone_number == "13911111111"

    def test_update_address_succeeds(self, regular_client, regular_user_obj):
        _link(regular_user_obj, address="旧地址")
        response = regular_client.patch(
            URL, {"address": "新地址"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        regular_user_obj.personnel.refresh_from_db()
        assert regular_user_obj.personnel.address == "新地址"

    def test_update_date_of_birth_succeeds(self, regular_client, regular_user_obj):
        import datetime
        _link(regular_user_obj)
        response = regular_client.patch(
            URL, {"date_of_birth": "1990-01-15"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        regular_user_obj.personnel.refresh_from_db()
        assert regular_user_obj.personnel.date_of_birth == datetime.date(1990, 1, 15)


@pytest.mark.django_db
class TestMyPersonnelPatchForbiddenFields:
    """PATCH 尝试改敏感字段应被 L1/L2 拦截。"""

    def test_update_name_is_ignored(self, regular_client, regular_user_obj):
        p = _link(regular_user_obj)
        original_name = p.name
        response = regular_client.patch(
            URL, {"name": "新姓名"}, format="json"
        )
        # 字段不在白名单,应被 L1 静默忽略
        assert response.status_code == status.HTTP_200_OK
        p.refresh_from_db()
        assert p.name == original_name

    def test_update_status_is_ignored(self, regular_client, regular_user_obj):
        p = _link(regular_user_obj, status="active")
        response = regular_client.patch(
            URL, {"status": "inactive"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        p.refresh_from_db()
        assert p.status == "active"

    def test_update_position_is_ignored(self, regular_client, regular_user_obj):
        from personnel.models import Position
        pos_old = Position.objects.create(name="旧岗")
        p = _link(regular_user_obj)
        p.position = pos_old
        p.save()
        pos_new = Position.objects.create(name="新岗")
        response = regular_client.patch(
            URL, {"position": pos_new.id}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        p.refresh_from_db()
        assert p.position_id == pos_old.id


@pytest.mark.django_db
class TestMyPersonnelNotification:
    """PATCH 成功后应发通知(自身信息变更)。"""

    def test_phone_update_creates_notification(self, regular_client, regular_user_obj):
        _link(regular_user_obj, phone_number="13800000000")
        assert Notification.objects.filter(user=regular_user_obj).count() == 0
        regular_client.patch(URL, {"phone_number": "13911111111"}, format="json")
        # 应至少有 1 条通知
        assert Notification.objects.filter(user=regular_user_obj).count() >= 1
