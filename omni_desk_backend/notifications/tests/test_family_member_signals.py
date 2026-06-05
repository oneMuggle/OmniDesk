"""P3-2 FamilyMember post_save 信号 — TDD 测试(RED 阶段)

FamilyMember 新增或更新时,通知 personnel 关联 user 确认。
- 首次创建(本人添加) → 通知确认
- 变更(改 contact_number 等) → 通知确认
- 无关联 user → 不通知
"""
import pytest

from notifications.models import Notification
from personnel.models import FamilyMember, Personnel


@pytest.mark.django_db
class TestFamilyMemberSignal:
    def test_create_triggers_confirmation_notification(self, regular_user_obj):
        p = Personnel.objects.create(name=regular_user_obj.username)
        regular_user_obj.personnel = p
        regular_user_obj.save()
        FamilyMember.objects.create(
            personnel=p, name="张三", relationship="配偶"
        )
        notif = Notification.objects.filter(
            user=regular_user_obj, type="emergency_contact"
        ).first()
        assert notif is not None
        assert "张三" in notif.content or "配偶" in notif.content

    def test_update_triggers_notification(self, regular_user_obj):
        p = Personnel.objects.create(name=regular_user_obj.username)
        regular_user_obj.personnel = p
        regular_user_obj.save()
        fm = FamilyMember.objects.create(
            personnel=p, name="张三", relationship="配偶", contact_number="13800000000"
        )
        # 清空初始通知
        Notification.objects.filter(user=regular_user_obj).delete()
        # 改电话
        fm.contact_number = "13900000000"
        fm.save()
        notif = Notification.objects.filter(
            user=regular_user_obj, type="emergency_contact"
        ).first()
        assert notif is not None
        assert "13900000000" in notif.content or "张三" in notif.content

    def test_no_user_account_does_not_notify(self, db):
        p = Personnel.objects.create(name="无账号人员")
        FamilyMember.objects.create(personnel=p, name="张三", relationship="配偶")
        assert Notification.objects.filter(type="emergency_contact").count() == 0
