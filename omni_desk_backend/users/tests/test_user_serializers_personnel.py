"""为 user_serializers.py 补覆盖度,验证 personnel → real_name 联动约定。

P1 设计约定:用户一旦关联 personnel,real_name 字段自动跟随 Personnel.name
并变只读(沿用 user_serializers.py:55-58 / 93-96 既有逻辑)。
"""
import pytest

from personnel.models import Personnel
from users.user_serializers import UserDetailSerializer, UserSerializer, UserAdminSerializer


@pytest.mark.django_db
class TestRealNameLinkedToPersonnel:
    """当 user 已关联 personnel,real_name 字段在 detail serializer 中应只读。"""

    def test_user_detail_serializer_real_name_readonly_when_personnel_linked(self, regular_user_obj):
        p = Personnel.objects.create(name=regular_user_obj.username)
        regular_user_obj.personnel = p
        regular_user_obj.real_name = "old value"
        regular_user_obj.save()
        # 用 instance 触发 __init__ 中的 real_name 只读设置
        serializer = UserDetailSerializer(instance=regular_user_obj)
        assert serializer.fields["real_name"].read_only is True

    def test_user_detail_serializer_real_name_editable_when_no_personnel(self, regular_user_obj):
        assert regular_user_obj.personnel is None
        serializer = UserDetailSerializer(instance=regular_user_obj)
        # 没有 personnel 时,real_name 应可编辑
        assert serializer.fields["real_name"].read_only is False

    def test_user_serializer_real_name_readonly_when_personnel_linked(self, regular_user_obj):
        p = Personnel.objects.create(name=regular_user_obj.username)
        regular_user_obj.personnel = p
        regular_user_obj.save()
        serializer = UserSerializer(instance=regular_user_obj)
        assert serializer.fields["real_name"].read_only is True


@pytest.mark.django_db
class TestGetPermissions:
    """UserSerializer.get_permissions 应返回 can_change / can_delete。"""

    def test_get_permissions_without_request_returns_false(self, regular_user_obj):
        serializer = UserSerializer(instance=regular_user_obj)
        result = serializer.get_permissions(regular_user_obj)
        assert result == {"can_change": False, "can_delete": False}

    def test_get_permissions_with_admin_request(self, admin_user_obj, regular_user_obj):
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = admin_user_obj
        context = {"request": request}
        serializer = UserSerializer(instance=regular_user_obj, context=context)
        result = serializer.get_permissions(regular_user_obj)
        # superuser 应有 change_customuser 权限
        assert result["can_change"] is True
        assert result["can_delete"] is True


@pytest.mark.django_db
class TestUserAdminSerializer:
    """UserAdminSerializer.create / update 应正确处理 phone_numbers 子表。"""

    def test_create_user_with_phone_numbers(self):
        data = {
            "username": "new_admin_user",
            "password": "test123",
            "phone_numbers": [{"number": "13800000001"}, {"number": "13800000002"}],
        }
        serializer = UserAdminSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()
        assert user.pk is not None
        assert user.phone_numbers.count() == 2
        numbers = sorted(user.phone_numbers.values_list("number", flat=True))
        assert numbers == ["13800000001", "13800000002"]

    def test_update_user_replaces_phone_numbers(self, regular_user_obj):
        from users.models import PhoneNumber
        PhoneNumber.objects.create(user=regular_user_obj, number="13800000010")
        PhoneNumber.objects.create(user=regular_user_obj, number="13800000011")
        assert regular_user_obj.phone_numbers.count() == 2
        serializer = UserAdminSerializer(
            instance=regular_user_obj,
            data={"username": regular_user_obj.username, "phone_numbers": [{"number": "13900000000"}]},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        regular_user_obj.refresh_from_db()
        assert regular_user_obj.phone_numbers.count() == 1
        assert regular_user_obj.phone_numbers.first().number == "13900000000"
