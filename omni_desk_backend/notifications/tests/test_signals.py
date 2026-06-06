"""P1 主题:Schedule 创建触发 personnel 关联用户的通知(signal 端到端验证)。

覆盖 notifications/signals.py:24-49 中 _get_user_from_personnel 与 _notify 调用。
"""
import pytest
from datetime import date

from events.models import Schedule
from notifications.models import Notification
from personnel.models import Personnel


@pytest.mark.django_db
class TestScheduleNotificationSignal:
    """Schedule 创建后应通过 signal 触发 personnel 关联用户的通知。"""

    def test_schedule_create_notifies_duty_person_user(self, regular_user_obj):
        """为 personnel 关联 user,创建 Schedule 后应收到通知。"""
        p = Personnel.objects.create(name=regular_user_obj.username)
        regular_user_obj.personnel = p
        regular_user_obj.save()
        Schedule.objects.create(
            duty_date=date(2026, 7, 1),
            duty_person=p,
        )
        notif = Notification.objects.filter(
            user=regular_user_obj, type="schedule_change"
        ).first()
        assert notif is not None
        assert "2026-07-01" in notif.content or "排班" in notif.title

    def test_schedule_without_user_account_does_not_notify(self, db):
        """personnel 没关联 user 时,创建 Schedule 不应发通知(无收件人)。"""
        p = Personnel.objects.create(name="无账号人员")
        Schedule.objects.create(
            duty_date=date(2026, 7, 2),
            duty_person=p,
        )
        # 无任何通知被发出
        assert Notification.objects.filter(type="schedule_change").count() == 0
