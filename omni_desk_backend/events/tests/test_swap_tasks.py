"""SP4: cleanup_expired_swap_requests Celery 任务 TDD 测试(RED 阶段)

决策 3B:TTL 48h。超期未处理的 pending 申请 → 改为 expired。
触发 SP3 信号(已实现)自动发 schedule_swap_expired 通知给三方。
"""
import datetime

import pytest
from django.utils import timezone

from events.models import Schedule, ScheduleSwapRequest
from events.tasks import cleanup_expired_swap_requests
from notifications.models import Notification
from personnel.models import Personnel


@pytest.fixture
def future_date():
    return (timezone.now() + datetime.timedelta(days=7)).date()


@pytest.fixture
def person_a(regular_user_obj):
    p = Personnel.objects.create(name=regular_user_obj.username)
    regular_user_obj.personnel = p
    regular_user_obj.save()
    return p


@pytest.fixture
def person_b(db):
    p = Personnel.objects.create(name="接收方-李四")
    return p


@pytest.fixture
def schedule_a(future_date, person_a):
    return Schedule.objects.create(duty_date=future_date, duty_person=person_a)


# ---- 主流程:过期清理 ----


@pytest.mark.django_db
class TestCleanupExpired:
    def test_expired_pending_becomes_expired(self, person_a, person_b, schedule_a):
        """超期 pending 申请 → status=expired。"""
        ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() - datetime.timedelta(hours=1),
        )
        result = cleanup_expired_swap_requests()
        swap = ScheduleSwapRequest.objects.get(original_schedule=schedule_a)
        assert swap.status == ScheduleSwapRequest.STATUS_EXPIRED
        assert "1" in result

    def test_non_expired_pending_untouched(self, person_a, person_b, schedule_a):
        """未过期 pending 申请 → 不变。"""
        ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=24),
        )
        cleanup_expired_swap_requests()
        swap = ScheduleSwapRequest.objects.get(original_schedule=schedule_a)
        assert swap.status == ScheduleSwapRequest.STATUS_PENDING

    def test_already_approved_untouched_even_if_expired(self, person_a, person_b, schedule_a):
        """已 approved 的申请不重新清理。"""
        swap = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() - datetime.timedelta(hours=1),
        )
        swap.apply_swap(approver=None)
        swap.save()
        cleanup_expired_swap_requests()
        swap.refresh_from_db()
        assert swap.status == ScheduleSwapRequest.STATUS_APPROVED


# ---- 信号触发:清理后应自动发通知 ----


@pytest.mark.django_db
class TestSignalFiresAfterCleanup:
    def test_cleanup_notifies_requester(self, person_a, person_b, schedule_a, regular_user_obj):
        """cleanup 后,SP3 信号自动给申请方发 expired 通知。"""
        ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() - datetime.timedelta(hours=1),
        )
        cleanup_expired_swap_requests()
        notifs = Notification.objects.filter(
            user=regular_user_obj, type="schedule_swap_expired"
        )
        assert notifs.count() == 1

    def test_cleanup_notifies_target(self, person_a, person_b, schedule_a):
        """cleanup 后,接收方也收到 expired 通知。"""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        b_user = User.objects.create_user(username="b_target_exp", password="x")
        b_user.personnel = person_b
        b_user.save()
        ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() - datetime.timedelta(hours=1),
        )
        cleanup_expired_swap_requests()
        notifs = Notification.objects.filter(
            user=b_user, type="schedule_swap_expired"
        )
        assert notifs.count() == 1


# ---- 批量清理 ----


@pytest.mark.django_db
class TestBatchCleanup:
    def test_multiple_expired_cleaned(self, person_a, person_b, schedule_a, db):
        """多个过期申请 → 全部清理。"""
        expired_count = 3
        for i in range(expired_count):
            Schedule.objects.create(
                duty_date=timezone.now().date() + datetime.timedelta(days=10 + i),
                duty_person=person_a,
            )
        schedules = Schedule.objects.filter(duty_person=person_a).order_by("id")
        for s in schedules[:expired_count]:
            ScheduleSwapRequest.objects.create(
                requester=person_a,
                original_schedule=s,
                target_personnel=person_b,
                reason=f"申请 {s.id}",
                expires_at=timezone.now() - datetime.timedelta(minutes=30),
            )
        result = cleanup_expired_swap_requests()
        assert f"{expired_count}" in result
        assert (
            ScheduleSwapRequest.objects.filter(
                status=ScheduleSwapRequest.STATUS_PENDING
            ).count()
            == 0
        )
        assert (
            ScheduleSwapRequest.objects.filter(
                status=ScheduleSwapRequest.STATUS_EXPIRED
            ).count()
            == expired_count
        )


# ---- 幂等性 ----


@pytest.mark.django_db
class TestIdempotent:
    def test_double_run_no_extra_side_effects(self, person_a, person_b, schedule_a):
        """二次跑同一任务:无副作用(已 expired 的不会再被处理)。"""
        ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() - datetime.timedelta(hours=1),
        )
        cleanup_expired_swap_requests()
        result2 = cleanup_expired_swap_requests()
        assert "0" in result2
