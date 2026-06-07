"""SP1-1: ScheduleSwapRequest 模型 TDD 测试(RED 阶段)

决策 1C:两人互认即生效。状态机:pending / approved / rejected_by_target / cancelled / expired。
- pending → approved(接收方 accept,ViewSet 内部调 apply_swap)
- pending → rejected_by_target(接收方 reject)
- pending → cancelled(申请方 cancel)
- pending → expired(系统 48h 超时)

决策 2C:target_schedule 可空(null = 单方面替班,有值 = 双向对调)。
决策 3B:expires_at 注入 48h,默认 settings.SWAP_REQUEST_TTL_HOURS。
决策 4A:不支持链式换班。
决策 5A:scope 暂只支持 duty_person,duty_leader 留后续(但模型预留字段)。
"""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from events.models import Schedule, ScheduleSwapRequest
from personnel.models import Personnel, Position


@pytest.fixture
def duty_date():
    """未来 7 天,避免过去日期校验。"""
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
def schedule_with_duty(duty_date, person_a):
    return Schedule.objects.create(duty_date=duty_date, duty_person=person_a)


# ---- 状态机常量 ----


class TestStatusChoices:
    def test_status_choices_contain_all_required(self):
        """5 个状态值都应存在(去掉了 accepted_by_target 中间态)。"""
        codes = {code for code, _ in ScheduleSwapRequest.STATUS_CHOICES}
        assert codes == {
            "pending",
            "approved",
            "rejected_by_target",
            "cancelled",
            "expired",
        }

    def test_default_status_is_pending(self):
        req = ScheduleSwapRequest()
        assert req.status == "pending"


# ---- 字段类型 ----


class TestFieldTypes:
    def test_dedupe_unique_constraint_per_active_schedule(self):
        """同一 original_schedule 同一时间只能有一个 active 申请(pending 状态唯一)。"""
        constraints = ScheduleSwapRequest._meta.constraints
        uniq = [c for c in constraints if c.name == "uniq_active_swap_per_schedule"]
        assert len(uniq) == 1
        assert uniq[0].condition is not None  # Q(status__in=...)

    def test_indexes_include_status_expires(self):
        """status + expires_at 复合索引必须存在(供 Celery 清理任务使用)。"""
        index_names = {i.name for i in ScheduleSwapRequest._meta.indexes}
        assert "swap_status_expires_idx" in index_names

    def test_expires_at_is_indexed(self):
        assert ScheduleSwapRequest._meta.get_field("expires_at").db_index is True

    def test_status_is_indexed(self):
        assert ScheduleSwapRequest._meta.get_field("status").db_index is True


# ---- L3 clean() 校验 ----


class TestCleanValidation:
    def test_self_swap_raises(self, schedule_with_duty, person_a, person_b):
        """L3:不能把班换给自己(requester == target_personnel)。"""
        req = ScheduleSwapRequest(
            requester=person_a,
            original_schedule=schedule_with_duty,
            target_personnel=person_a,  # 换给自己
            target_schedule=None,
            reason="测试自换",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        with pytest.raises(ValidationError) as exc:
            req.clean()
        assert "target_personnel" in exc.value.message_dict

    def test_past_date_raises(self, person_a, person_b):
        """L3:无法对已过去的排班发起申请。"""
        past = Schedule.objects.create(
            duty_date=timezone.now().date() - datetime.timedelta(days=1),
            duty_person=person_a,
        )
        req = ScheduleSwapRequest(
            requester=person_a,
            original_schedule=past,
            target_personnel=person_b,
            reason="过去日期",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        with pytest.raises(ValidationError) as exc:
            req.clean()
        assert "original_schedule" in exc.value.message_dict

    def test_non_duty_person_raises(self, person_a, person_b, schedule_with_duty, db):
        """L3:requester 不是原排班的 duty_person,无权发起。"""
        person_c = Personnel.objects.create(name="路人-丙")
        req = ScheduleSwapRequest(
            requester=person_c,  # 路人丙,非值班员 person_a
            original_schedule=schedule_with_duty,
            target_personnel=person_b,
            reason="无权限",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        with pytest.raises(ValidationError) as exc:
            req.clean()
        assert "requester" in exc.value.message_dict

    def test_expires_at_in_past_raises(self, schedule_with_duty, person_a, person_b):
        """L3:失效时间已过,不允许。"""
        req = ScheduleSwapRequest(
            requester=person_a,
            original_schedule=schedule_with_duty,
            target_personnel=person_b,
            reason="已过期",
            expires_at=timezone.now() - datetime.timedelta(hours=1),
        )
        with pytest.raises(ValidationError) as exc:
            req.clean()
        assert "expires_at" in exc.value.message_dict

    def test_valid_request_passes(self, schedule_with_duty, person_a, person_b):
        """合法申请应通过校验。"""
        req = ScheduleSwapRequest(
            requester=person_a,
            original_schedule=schedule_with_duty,
            target_personnel=person_b,
            reason="出差",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        req.clean()  # 不抛


# ---- apply_swap 原子操作(为后续 ViewSet 准备) ----


class TestApplySwap:
    def test_apply_swap_duty_person(self, schedule_with_duty, person_a, person_b):
        """accept 后,原排班的 duty_person 改为 target_personnel。"""
        req = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_with_duty,
            target_personnel=person_b,
            reason="出差",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        req.apply_swap(approver=person_b.user_account if hasattr(person_b, "user_account") else None)
        schedule_with_duty.refresh_from_db()
        assert schedule_with_duty.duty_person_id == person_b.id
        assert req.status == "approved"

    def test_apply_swap_two_way(self, duty_date, person_a, person_b):
        """双向对调:schedule_a.duty_person ↔ schedule_b.duty_person。"""
        schedule_a = Schedule.objects.create(duty_date=duty_date, duty_person=person_a)
        schedule_b = Schedule.objects.create(
            duty_date=duty_date + datetime.timedelta(days=1),
            duty_person=person_b,
        )
        req = ScheduleSwapRequest.objects.create(
            requester=person_a,
            original_schedule=schedule_a,
            target_personnel=person_b,
            target_schedule=schedule_b,
            reason="换班对调",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        req.apply_swap(approver=None)
        schedule_a.refresh_from_db()
        schedule_b.refresh_from_db()
        assert schedule_a.duty_person_id == person_b.id
        assert schedule_b.duty_person_id == person_a.id
