"""P3-1 Personnel pre/post_save 信号 — TDD 测试(RED 阶段)

当 Personnel.position 或 department 字段变更时,通过 pre_save 捕获旧值,
post_save 时对比,触发"岗位/部门变动"通知给关联 user。
- 首次创建不通知
- 无关联 user 不通知
- 多字段同时变更 → 一次性合并通知
"""
import pytest

from notifications.models import Notification
from personnel.models import Personnel, Position


@pytest.mark.django_db
class TestPersonnelPositionChange:
    """岗位变更应触发通知。"""

    def test_position_change_triggers_notification(self, regular_user_obj):
        p_old = Position.objects.create(name="旧岗")
        p_new = Position.objects.create(name="新岗")
        p = Personnel.objects.create(name=regular_user_obj.username, position=p_old)
        regular_user_obj.personnel = p
        regular_user_obj.save()
        # 改岗位
        p.position = p_new
        p.save()
        notif = Notification.objects.filter(
            user=regular_user_obj, type="position_changed"
        ).first()
        assert notif is not None
        assert "新岗" in notif.content or "旧岗" in notif.content

    def test_first_creation_does_not_notify(self, regular_user_obj):
        p_new = Position.objects.create(name="首岗")
        Personnel.objects.create(name=regular_user_obj.username, position=p_new)
        assert Notification.objects.filter(type="position_changed").count() == 0

    def test_no_user_account_does_not_notify(self, db):
        p_old = Position.objects.create(name="旧岗")
        p_new = Position.objects.create(name="新岗")
        p = Personnel.objects.create(name="无账号人员", position=p_old)
        p.position = p_new
        p.save()
        # 无任何通知
        assert Notification.objects.filter(type="position_changed").count() == 0

    def test_no_position_change_does_not_notify(self, regular_user_obj):
        """仅改其他字段(如 address),岗位不变则不应通知。"""
        p = Personnel.objects.create(
            name=regular_user_obj.username,
            address="旧地址",
        )
        regular_user_obj.personnel = p
        regular_user_obj.save()
        p.address = "新地址"
        p.save()
        assert Notification.objects.filter(type="position_changed").count() == 0


@pytest.mark.django_db
class TestPersonnelDepartmentChange:
    """部门变更应触发通知。"""

    def test_department_change_triggers_notification(self, regular_user_obj):
        p = Personnel.objects.create(
            name=regular_user_obj.username, department="旧部门"
        )
        regular_user_obj.personnel = p
        regular_user_obj.save()
        p.department = "新部门"
        p.save()
        notif = Notification.objects.filter(
            user=regular_user_obj, type="position_changed"
        ).first()
        assert notif is not None
        assert "部门" in notif.content

    def test_combined_position_and_department_change(self, regular_user_obj):
        p_old = Position.objects.create(name="旧岗")
        p = Personnel.objects.create(
            name=regular_user_obj.username,
            position=p_old,
            department="旧部门",
        )
        regular_user_obj.personnel = p
        regular_user_obj.save()
        p_new = Position.objects.create(name="新岗")
        p.position = p_new
        p.department = "新部门"
        p.save()
        notif = Notification.objects.filter(
            user=regular_user_obj, type="position_changed"
        ).first()
        assert notif is not None
        # 应同时包含岗位和部门信息
        assert "新岗" in notif.content
        assert "新部门" in notif.content
