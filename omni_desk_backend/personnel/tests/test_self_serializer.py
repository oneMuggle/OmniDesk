"""P2-1 PersonnelSelfSerializer — TDD 测试(RED 阶段)

设计目标(详见 plan 文档 §4.1 字段权限矩阵):
- 用户可写字段:date_of_birth, phone_number, address
- 用户只读字段:id, name, hire_date, department, position, status, id_card_number(脱敏)
- 子表字段:educations, work_experiences, family_members(嵌套)
- HR 视角:PersonnelHRSerializer 可看到 id_card_number,但仍受其它权限约束
"""
import pytest
from rest_framework import serializers

from personnel.models import Personnel
from personnel.serializers import PersonnelSelfSerializer


@pytest.mark.django_db
class TestPersonnelSelfSerializerReadOnlyFields:
    """只读字段不应出现在可写字段集合中。"""

    def test_readonly_fields_includes_sensitive(self):
        """姓名/工号/入职/部门/职位/状态 应为只读。"""
        s = PersonnelSelfSerializer()
        for field_name in ("id", "name", "hire_date", "department", "position", "status"):
            assert field_name in s.fields, f"{field_name} 应在 fields 中"
            assert s.fields[field_name].read_only is True, f"{field_name} 应为只读"

    def test_writable_fields_are_limited(self):
        """可写字段应仅限于 date_of_birth / phone_number / address。"""
        s = PersonnelSelfSerializer()
        writable = {n for n, f in s.fields.items() if not f.read_only}
        assert writable == {"date_of_birth", "phone_number", "address"}


@pytest.mark.django_db
class TestPersonnelSelfSerializerRoundTrip:
    """Serializer 实际读写行为。"""

    def test_user_can_update_phone_number(self, regular_user_obj):
        p = Personnel.objects.create(
            name=regular_user_obj.username,
            phone_number="13800000000",
        )
        s = PersonnelSelfSerializer(
            instance=p,
            data={"phone_number": "13911111111"},
            partial=True,
        )
        assert s.is_valid(), s.errors
        s.save()
        p.refresh_from_db()
        assert p.phone_number == "13911111111"

    def test_user_cannot_change_name_via_serializer(self, regular_user_obj):
        p = Personnel.objects.create(name="原姓名")
        s = PersonnelSelfSerializer(
            instance=p,
            data={"name": "新姓名"},
            partial=True,
        )
        assert s.is_valid(), s.errors
        s.save()
        p.refresh_from_db()
        # name 字段是只读,即使 PATCH 提交,也不会被改
        assert p.name == "原姓名"

    def test_user_cannot_change_status_via_serializer(self, regular_user_obj):
        p = Personnel.objects.create(name="测试", status="active")
        s = PersonnelSelfSerializer(
            instance=p,
            data={"status": "inactive"},
            partial=True,
        )
        assert s.is_valid(), s.errors
        s.save()
        p.refresh_from_db()
        assert p.status == "active"  # 没被改


@pytest.mark.django_db
class TestPersonnelSelfSerializerReadRepresentation:
    """序列化输出应符合设计(只读字段在 to_representation 中仍可读)。"""

    def test_serializer_outputs_user_visible_fields(self, regular_user_obj):
        p = Personnel.objects.create(
            name=regular_user_obj.username,
            phone_number="13800000000",
            address="某地址",
        )
        s = PersonnelSelfSerializer(instance=p)
        data = s.data
        assert data["name"] == regular_user_obj.username
        assert data["phone_number"] == "13800000000"
        assert data["address"] == "某地址"
