"""SP3: ScheduleSwapRequest Signal 测试(RED 阶段)

决策 1C:两人互认即生效 + HR 知情。所有状态变化都:
1. 通知申请方 / 接收方
2. 通知 HR 组每个用户(知情)

触发场景:
- create: 通知接收方 + HR 组
- accept: 通知申请方 + HR 组
- reject: 通知申请方 + HR 组
- cancel: 通知接收方 + HR 组
- 系统 expire(由 Celery 触发,本次不测)

L3 防护:信号处理 try/except,失败仅 log 不抛(不阻塞主流程)。
"""

import datetime

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from events.models import Schedule, ScheduleSwapAuditLog, ScheduleSwapRequest
from notifications.models import Notification
from personnel.models import Personnel


@pytest.fixture
def future_date():
    return (timezone.now() + datetime.timedelta(days=7)).date()


@pytest.fixture
def hr_user(db):
    from django.contrib.auth import get_user_model

    u = get_user_model().objects.create_user(username="hr_user_signal", password="x")
    grp, _ = Group.objects.get_or_create(name="Manager")
    u.groups.add(grp)
    return u


@pytest.fixture
def person_a(regular_user_obj):
    p = Personnel.objects.create(name=regular_user_obj.username)
    regular_user_obj.personnel = p
    regular_user_obj.save()
    return p


@pytest.fixture
def person_b(db):
    from django.contrib.auth import get_user_model

    p = Personnel.objects.create(name="接收方-李四")
    user_b = get_user_model().objects.create_user(username="b_user_signal", password="x")
    user_b.personnel = p
    user_b.save()
    return p


@pytest.fixture
def person_c(db):
    return Personnel.objects.create(name="路人-丙")


@pytest.fixture
def schedule_a(future_date, person_a):
    return Schedule.objects.create(duty_date=future_date, duty_person=person_a)


# ---- create 触发 ----


@pytest.mark.django_db
class TestCreateTrigger:
    def test_creating_swap_notifies_target(self, regular_user_obj, person_a, person_b, schedule_a, hr_user):
        """创建换班 → 通知接收方(b_user_signal)。"""
        ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        target_notifs = Notification.objects.filter(user=person_b.user_account, type="schedule_swap_requested")
        assert target_notifs.count() == 1
        assert person_a.name in target_notifs.first().content

    def test_creating_swap_notifies_hr(self, regular_user_obj, person_a, person_b, schedule_a, hr_user):
        """创建换班 → 同时通知 HR 组(决策 1C 知情角色)。"""
        ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        hr_notifs = Notification.objects.filter(user=hr_user, type="schedule_swap_requested")
        assert hr_notifs.count() == 1

    def test_no_hr_group_no_hr_notification(self, person_c, person_b, db):
        """HR 组无成员 → 不报错(空迭代)。"""
        from datetime import timedelta

        from django.contrib.auth import get_user_model
        from django.utils import timezone as _tz

        User = get_user_model()
        # 用 person_c(路人丙)做 requester,person_b 做 target
        regular = User.objects.create_user(username="regular_no_hr", password="x")
        regular.personnel = person_c
        regular.save()
        # 单独建排班给 person_c
        sch = Schedule.objects.create(
            duty_date=timezone.now().date() + datetime.timedelta(days=10),
            duty_person=person_c,
        )
        ScheduleSwapRequest.objects.create(
            requester=person_c,
            original_schedule=sch,
            target_personnel=person_b,
            reason="测试",
            expires_at=_tz.now() + timedelta(hours=48),
        )
        assert Notification.objects.filter(type="schedule_swap_requested").count() >= 1


# ---- accept 触发(目标方 user_account 自动生效) ----


@pytest.mark.django_db
class TestAcceptTrigger:
    def test_accept_notifies_requester(self, person_a, person_b, schedule_a):
        """目标方 accept → 通知申请方(swap_approved)。"""
        swap = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        swap.apply_swap(approver=person_b.user_account)
        swap.save()
        notifs = Notification.objects.filter(user=person_a.user_account, type="schedule_swap_approved")
        assert notifs.count() == 1

    def test_accept_notifies_hr_group(self, person_a, person_b, schedule_a, hr_user):
        """accept → HR 组也收到 approved 通知。"""
        swap = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        swap.apply_swap(approver=person_b.user_account)
        swap.save()
        notifs = Notification.objects.filter(user=hr_user, type="schedule_swap_approved")
        assert notifs.count() == 1


# ---- reject 触发 ----


@pytest.mark.django_db
class TestRejectTrigger:
    def test_reject_notifies_requester(self, person_a, person_b, schedule_a):
        """目标方 reject → 通知申请方。"""
        swap = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        swap.status = ScheduleSwapRequest.STATUS_REJECTED
        swap.target_decided_at = timezone.now()
        swap.save()
        notifs = Notification.objects.filter(user=person_a.user_account, type="schedule_swap_rejected")
        assert notifs.count() == 1


# ---- cancel 触发 ----


@pytest.mark.django_db
class TestCancelTrigger:
    def test_cancel_notifies_target(self, person_a, person_b, schedule_a):
        """申请方 cancel → 通知接收方。"""
        swap = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        swap.status = ScheduleSwapRequest.STATUS_CANCELLED
        swap.save()
        notifs = Notification.objects.filter(user=person_b.user_account, type="schedule_swap_cancelled")
        assert notifs.count() == 1


# ---- L3:信号不阻塞主流程 ----


@pytest.mark.django_db
class TestSignalFailureDoesNotBlock:
    def test_notification_failure_does_not_break_save(self, person_a, person_b, schedule_a, monkeypatch):
        """即使 NotificationService 抛异常,ScheduleSwapRequest.save() 仍应成功。"""
        from events import signals as swap_signals

        def _broken(*args, **kwargs):
            raise RuntimeError("simulated notification failure")

        monkeypatch.setattr(swap_signals, "_notify_hr_group", _broken)
        swap = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        assert swap.pk is not None
