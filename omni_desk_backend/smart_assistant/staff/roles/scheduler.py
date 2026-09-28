"""排班管理员：巡检未来 7 天的排班冲突（S4-1）。

| 冲突 | 处理 |
|---|---|
| 值班人员当天是计划中/进行中试验的责任人 | 推荐接替人，给值班人员创建「发起换班申请」待确认事项 |
| 值班人员或值班领导已离职 | 通知角色负责人（未设置时通知智能助手管理员） |
| 同一人同日既是值班人员又是值班领导 | 同上 |

确认后以值班人员本人身份发起换班申请，之后走正常换班流程（接收方同意后生效）。
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from ...writes.preview import build_preview, change
from ..runtime import RoleRunner, admin_recipients, day_start

HORIZON_DAYS = 7
LOAD_WINDOW_DAYS = 30
ACTIVE_TRIAL_STATUSES = ("planned", "in_progress")


def _user_of(person):
    try:
        user = person.user_account
    except Exception:
        return None
    return user if user is not None and user.is_active else None


def trials_on(day, person=None):
    """当天有时间段、且状态为计划中/进行中的试验。"""
    from events.models import Trial

    qs = Trial.objects.filter(
        status__in=ACTIVE_TRIAL_STATUSES,
        time_slots__start_time__lt=day_start(day + timedelta(days=1)),
        time_slots__end_time__gt=day_start(day),
    )
    if person is not None:
        qs = qs.filter(responsible_persons=person)
    return qs.distinct()


def pick_candidate(schedule, person):
    """推荐接替人：在职且有账号、非本人、前后 1 天无值班、当天不是试验责任人，未来 30 天值班最少者优先。"""
    from events.models import Schedule
    from personnel.models import Personnel

    day = schedule.duty_date
    nearby = Schedule.objects.filter(duty_date__range=(day - timedelta(days=1), day + timedelta(days=1)))
    busy = {pk for pk in nearby.values_list("duty_person_id", flat=True) if pk}
    busy |= {pk for pk in nearby.filter(duty_date=day).values_list("duty_leader_id", flat=True) if pk}
    busy |= {pk for pk in trials_on(day).values_list("responsible_persons__id", flat=True) if pk}
    today = timezone.localdate()
    window = (today, today + timedelta(days=LOAD_WINDOW_DAYS))
    return (
        Personnel.objects.filter(status="active", user_account__isnull=False, user_account__is_active=True)
        .exclude(pk=person.pk)
        .exclude(pk__in=busy)
        .annotate(load=Count("duty_schedules", filter=Q(duty_schedules__duty_date__range=window)))
        .order_by("load", "id")
        .first()
    )


class SchedulerRunner(RoleRunner):
    def run(self):
        from events.models import Schedule

        today = self.ctx.today
        schedules = Schedule.objects.filter(
            duty_date__range=(today, today + timedelta(days=HORIZON_DAYS - 1))
        ).select_related("duty_person", "duty_leader")
        for schedule in schedules.order_by("duty_date"):
            self.ctx.stats["schedules"] += 1
            self.check_inactive(schedule)
            self.check_same_person(schedule)
            self.check_trial(schedule)

    # ------------------------------------------------------------------
    def _notify_admins(self, title: str, content: str, dedupe_key: str):
        for user in admin_recipients(self.ctx.profile):
            self.ctx.notify(user, title=title, content=content, link="/control-panel/schedule", dedupe_key=dedupe_key)

    def check_inactive(self, schedule):
        for role, person in (("值班人员", schedule.duty_person), ("值班领导", schedule.duty_leader)):
            if person is not None and person.status != "active":
                self.ctx.stats["conflict_inactive"] += 1
                self._notify_admins(
                    f"排班提醒：{schedule.duty_date:%m-%d} 的{role}已离职",
                    f"{schedule.duty_date.isoformat()} 的{role}「{person.name}」已是离职状态，请调整排班。",
                    f"agent_scheduler:inactive:{schedule.pk}:{person.pk}",
                )

    def check_same_person(self, schedule):
        if schedule.duty_person_id and schedule.duty_person_id == schedule.duty_leader_id:
            self.ctx.stats["conflict_same_person"] += 1
            self._notify_admins(
                f"排班提醒：{schedule.duty_date:%m-%d} 值班人员与值班领导是同一人",
                f"{schedule.duty_date.isoformat()} 的值班人员和值班领导都是「{schedule.duty_person.name}」，请调整排班。",
                f"agent_scheduler:same:{schedule.pk}",
            )

    def check_trial(self, schedule):
        from events.models import ScheduleSwapRequest

        person = schedule.duty_person
        if person is None or person.status != "active":
            return
        trials = list(trials_on(schedule.duty_date, person)[:5])
        if not trials:
            return
        self.ctx.stats["conflict_trial"] += 1
        titles = "、".join(t.title for t in trials)
        user = _user_of(person)
        if user is None:
            self._notify_admins(
                f"排班提醒：{schedule.duty_date:%m-%d} 值班与试验冲突",
                f"{schedule.duty_date.isoformat()} 的值班人员「{person.name}」当天负责试验：{titles}；"
                "该人员未关联账号，请管理员协调。",
                f"agent_scheduler:trial:{schedule.pk}:{person.pk}",
            )
            return
        if ScheduleSwapRequest.objects.filter(
            original_schedule=schedule, status=ScheduleSwapRequest.STATUS_PENDING
        ).exists():
            self.ctx.stats["skipped_swap_pending"] += 1
            return
        candidate = pick_candidate(schedule, person)
        expires_at = day_start(schedule.duty_date)
        if candidate is None or expires_at <= timezone.now():
            self.ctx.notify(
                user,
                title=f"排班提醒：{schedule.duty_date:%m-%d} 值班与试验冲突",
                content=f"你在 {schedule.duty_date.isoformat()} 值班，当天还负责试验：{titles}。"
                + ("没有找到合适的接替人，" if candidate is None else "")
                + "如需换班请尽快处理。",
                link="/smart-assistant",
                dedupe_key=f"agent_scheduler:trial:{schedule.pk}:{person.pk}",
            )
            return
        reason = f"当天负责试验：{titles}"[:200]
        preview = build_preview(
            action="发起换班申请",
            target_type="值班",
            target_label=f"{schedule.duty_date.isoformat()} 值班人员",
            changes=[change("duty_person", "值班人员", person.name, candidate.name)],
            affected_label="条换班申请",
            permission_source="本人排班",
            reversible=False,
            items=[f"冲突试验：{t.title}" for t in trials],
            warnings=[
                f"确认后将向「{candidate.name}」发送换班申请，对方同意后生效。",
                "如需换给其他人，请取消后在智能助手里直接说明。",
            ],
        )
        self.ctx.propose(
            user,
            kind="swap_request",
            title=f"{schedule.duty_date:%m-%d} 值班与试验冲突，建议与{candidate.name}换班",
            fields={
                "schedule_id": schedule.pk,
                "duty_date": schedule.duty_date.isoformat(),
                "requester_personnel_id": person.pk,
                "target_personnel_id": candidate.pk,
                "reason": reason,
            },
            preview=preview,
            dedupe_key=f"swap:{schedule.pk}:{person.pk}",
            expires_at=expires_at,
            content=f"你在 {schedule.duty_date.isoformat()} 值班，当天还负责试验：{titles}。"
            f"建议与「{candidate.name}」换班，点击后在智能助手里确认是否发起换班申请。",
        )
