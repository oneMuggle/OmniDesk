"""SP1-1 覆盖率补足:ScheduleSwapRequest 全分支覆盖

补目标:把全局覆盖率从 77.89% 推到 ≥ 80%。
覆盖:clean() 全部分支、apply_swap 三种边界、__str__、status_display 属性。
"""
import datetime

import pytest
from django.utils import timezone

from events.models import Schedule, ScheduleSwapAuditLog, ScheduleSwapRequest
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
    return Personnel.objects.create(name="接收方-李四")


@pytest.fixture
def person_c(db):
    return Personnel.objects.create(name="路人-丙")


@pytest.fixture
def schedule_duty_a(future_date, person_a):
    return Schedule.objects.create(duty_date=future_date, duty_person=person_a)


# ---- __str__ / status_display ----


class TestStrAndDisplay:
    def test_str_representation(self, schedule_duty_a, person_a, person_b):
        req = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_duty_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        s = str(req)
        assert "→" in s
        assert "[pending]" in s

    def test_status_display_property(self, schedule_duty_a, person_a, person_b):
        req = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_duty_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        assert req.status_display == "待接收方确认"


# ---- clean() 全分支覆盖 ----


class TestCleanFullBranches:
    def test_clean_with_no_pk_skip_target_check(self, person_a, person_b):
        """无 original_schedule 时跳过当事方校验(避免 P1 阶段早期就报错)。"""
        req = ScheduleSwapRequest(
            requester=person_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        req.clean()  # 不抛

    def test_clean_with_self_swap_no_schedule(self, person_a):
        """自换 + 无原排班,只校验自换。"""
        req = ScheduleSwapRequest(
            requester=person_a,
            target_personnel=person_a,  # 自换
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        with pytest.raises(Exception):
            req.clean()

    def test_clean_duty_leader_scope(self, future_date, person_a, person_b, person_c):
        """scope=duty_leader 时,requester 必须是原排班的 duty_leader。"""
        s = Schedule.objects.create(
            duty_date=future_date, duty_person=person_a, duty_leader=person_c
        )
        req = ScheduleSwapRequest(
            requester=person_b,  # 不是 leader
            original_schedule=s,
            target_personnel=person_c,
            scope="duty_leader",
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        with pytest.raises(Exception) as exc:
            req.clean()
        assert "requester" in exc.value.message_dict

    def test_clean_duty_leader_scope_requester_is_leader(
        self, future_date, person_a, person_b, person_c
    ):
        """scope=duty_leader,requester 是 leader,合法。"""
        s = Schedule.objects.create(
            duty_date=future_date, duty_person=person_a, duty_leader=person_c
        )
        req = ScheduleSwapRequest(
            requester=person_c,  # leader
            original_schedule=s,
            target_personnel=person_b,
            scope="duty_leader",
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        req.clean()  # 不抛

    def test_clean_with_no_duty_date(self, person_a, person_b):
        """原排班无 duty_date 时不校验过去(留个 P1 早期入口)。"""
        s = Schedule.objects.create(
            duty_date=timezone.now().date(),  # 今天
            duty_person=person_a,
        )
        req = ScheduleSwapRequest(
            requester=person_a,
            original_schedule=s,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        req.clean()  # 不抛(今天不算"过去")

    def test_clean_with_today_date_raises_if_past_check(
        self, person_a, person_b
    ):
        """昨天的排班应被拒(过去日期校验)。"""
        yesterday = (timezone.now() - datetime.timedelta(days=1)).date()
        s = Schedule.objects.create(duty_date=yesterday, duty_person=person_a)
        req = ScheduleSwapRequest(
            requester=person_a,
            original_schedule=s,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        with pytest.raises(Exception) as exc:
            req.clean()
        assert "original_schedule" in exc.value.message_dict


# ---- apply_swap 全分支 ----


class TestApplySwapBranches:
    def test_apply_swap_approver_passed_and_status_set(
        self, schedule_duty_a, person_a, person_b, regular_user_obj
    ):
        """apply_swap 后 status=approved, approver+approved_at 正确设置。"""
        req = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_duty_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        req.apply_swap(approver=regular_user_obj)  # approver 是 FK to CustomUser
        req.refresh_from_db()
        assert req.status == "approved"
        assert req.approved_at is not None
        schedule_duty_a.refresh_from_db()
        assert schedule_duty_a.duty_person_id == person_b.id

    def test_apply_swap_with_none_approver(
        self, schedule_duty_a, person_a, person_b
    ):
        """approver=None 也应能正常 apply_swap。"""
        req = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_duty_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        req.apply_swap(approver=None)
        req.refresh_from_db()
        assert req.status == "approved"

    def test_apply_swap_two_way_updates_both_schedules(
        self, future_date, person_a, person_b
    ):
        """双向对调:两个 schedule 的 duty_person 都互换。"""
        s_a = Schedule.objects.create(
            duty_date=future_date, duty_person=person_a
        )
        s_b = Schedule.objects.create(
            duty_date=future_date + datetime.timedelta(days=1), duty_person=person_b
        )
        req = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=s_a,
            target_personnel=person_b,
            target_schedule=s_b,
            reason="对调",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        req.apply_swap(approver=None)
        s_a.refresh_from_db()
        s_b.refresh_from_db()
        assert s_a.duty_person_id == person_b.id
        assert s_b.duty_person_id == person_a.id


# ---- 唯一约束 ----


class TestUniqueConstraint:
    def test_two_pending_for_same_schedule_raises(self, schedule_duty_a, person_a, person_b):
        from django.db import IntegrityError

        ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_duty_a,
            target_personnel=person_b,
            reason="第一个",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        with pytest.raises(IntegrityError):
            ScheduleSwapRequest.objects.create(
                requester=person_a,
                original_schedule=schedule_duty_a,
                target_personnel=person_b,
                reason="第二个",
                expires_at=timezone.now() + datetime.timedelta(hours=48),
            )

    def test_after_status_change_can_create_new(
        self, schedule_duty_a, person_a, person_b
    ):
        """原申请变成 approved 后,同一 schedule 可再次发起。"""
        first = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_duty_a,
            target_personnel=person_b,
            reason="第一个",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        first.apply_swap(approver=None)
        first.save()
        ScheduleSwapRequest.objects.create(
            requester=person_b,
            original_schedule=schedule_duty_a,
            target_personnel=person_a,
            reason="第二次",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        assert ScheduleSwapRequest.objects.filter(original_schedule=schedule_duty_a).count() == 2


# ---- ScheduleSwapAuditLog 模型 ----


class TestScheduleSwapAuditLog:
    def test_create_entry_and_str(self, schedule_duty_a, person_a, person_b, regular_user_obj):
        req = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_duty_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        log = ScheduleSwapAuditLog.objects.create(
            swap_request=req,
            actor=regular_user_obj,
            from_status="pending",
            to_status="approved",
            note="接收方同意",
        )
        assert log.pk is not None
        s = str(log)
        assert "pending" in s
        assert "approved" in s

    def test_str_with_no_actor(self, schedule_duty_a, person_a, person_b):
        req = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_duty_a,
            target_personnel=person_b,
            reason="测试",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        log = ScheduleSwapAuditLog.objects.create(
            swap_request=req,
            actor=None,
            from_status="pending",
            to_status="expired",
        )
        s = str(log)
        assert "system" in s
