"""数字员工运行框架（S4-1）。

- ``run_profile``：执行一次角色运行（关闭则跳过，同角色不并发，异常记为 failed）。
- ``RunContext``：角色能做的三类动作——``notify`` / ``propose`` / ``llm``。每个动作都写
  ``AgentRunEvent`` 审计，并受角色的每日配额约束；超额时跳过动作或降级为模板，不会中断运行。

数字员工只能「发起 + 请求确认」：需要改业务数据的动作一律通过 ``propose`` 生成
待确认事项，由当事人在智能助手里确认后才执行（见 ``staff.proposals``）。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")

#: 角色 key → Runner 类的点分路径
RUNNERS: dict[str, str] = {
    "secretary": "smart_assistant.staff.roles.secretary.SecretaryRunner",
    "scheduler": "smart_assistant.staff.roles.scheduler.SchedulerRunner",
    "compliance": "smart_assistant.staff.roles.compliance.ComplianceRunner",
}

#: 超过这个时长仍为 running 的运行视为已中断（worker 崩溃等），不再阻止新运行
STALE_RUN_AFTER = timedelta(hours=1)
PROPOSAL_TTL = timedelta(hours=48)


def day_start(day) -> datetime:
    """本地时区某天 00:00 的 aware datetime。"""
    return timezone.make_aware(datetime.combine(day, time.min))


def record_event(profile, event_type: str, *, run=None, user=None, **payload):
    from smart_assistant.models import AgentRunEvent

    return AgentRunEvent.objects.create(profile=profile, run=run, event_type=event_type, user=user, payload=payload)


def usage_today(profile, today=None) -> dict:
    """当天已用的动作数与 LLM 调用数（按审计事件统计）。"""
    from smart_assistant.models import AgentRunEvent

    since = day_start(today or timezone.localdate())
    events = AgentRunEvent.objects.filter(profile=profile, created_at__gte=since)
    return {
        "actions": events.filter(event_type__in=AgentRunEvent.ACTION_EVENTS).count(),
        "llm_calls": events.filter(event_type="llm.call").count(),
    }


def admin_recipients(profile):
    """角色负责人；未设置时为全部智能助手管理员（超级用户与 Admin 组）。"""
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    if profile.owner_id and profile.owner.is_active:
        return [profile.owner]
    User = get_user_model()
    return list(User.objects.filter(Q(is_superuser=True) | Q(groups__name="Admin"), is_active=True).distinct())


class RoleRunner:
    """角色基类：子类实现 ``run()``，通过 ``self.ctx`` 执行动作。"""

    def __init__(self, ctx: RunContext):
        self.ctx = ctx

    def run(self) -> None:  # pragma: no cover - 抽象方法
        raise NotImplementedError


class RunContext:
    def __init__(self, profile, run=None, today=None):
        self.profile = profile
        self.run = run
        self.today = today or timezone.localdate()
        self.stats: Counter = Counter()
        used = usage_today(profile, self.today)
        self._actions_used = used["actions"]
        self._llm_used = used["llm_calls"]
        self.action_quota_hit = False
        self.llm_quota_hit = False
        self.llm_fallbacks = 0

    # ------------------------------------------------------------------ 审计
    def event(self, event_type: str, user=None, **payload):
        return record_event(self.profile, event_type, run=self.run, user=user, **payload)

    @property
    def degraded(self) -> bool:
        return self.action_quota_hit or self.llm_quota_hit or self.llm_fallbacks > 0

    # ------------------------------------------------------------------ 配额
    def _take_action(self) -> bool:
        quota = self.profile.daily_action_quota
        if self._actions_used >= quota:
            self.stats["skipped_quota"] += 1
            if not self.action_quota_hit:
                self.action_quota_hit = True
                self.event("quota.exceeded", kind="action", quota=quota)
                self._notify_owner_quota(quota)
            return False
        self._actions_used += 1
        return True

    def _notify_owner_quota(self, quota: int):
        """动作配额用完时提醒负责人一次（不计入配额，按天去重）。"""
        from notifications.service import NotificationService

        for user in admin_recipients(self.profile)[:5]:
            NotificationService.create(
                user=user,
                type="system",
                title=f"数字员工「{self.profile.name}」今日动作配额已用完",
                content=f"每日动作配额 {quota} 次已用完，今天剩余的提醒和待确认事项已跳过。可在「AI 管理 → 数字员工」调整配额。",
                link="/control-panel/ai/staff",
                dedupe_key=f"agent_quota:{self.profile.key}:{self.today.isoformat()}",
            )

    # ------------------------------------------------------------------ 动作
    def notify(self, user, *, title, content, link="", dedupe_key="", type="agent_notify", priority=None) -> bool:
        """发送站内通知。同一用户同一去重键当天已发过则跳过（不计配额）。"""
        from notifications.models import Notification
        from notifications.service import NotificationService

        if (
            dedupe_key
            and Notification.objects.filter(
                user=user, type=type, dedupe_key=dedupe_key, created_at__gte=day_start(self.today)
            ).exists()
        ):
            self.stats["skipped_duplicate"] += 1
            return False
        if not self._take_action():
            return False
        NotificationService.create(
            user=user,
            type=type,
            title=title[:200],
            content=content,
            link=link,
            priority=priority or Notification.PRIORITY_NORMAL,
            dedupe_key=dedupe_key,
        )
        self.stats["notifications"] += 1
        self.event("notify.sent", user=user, title=title[:100], dedupe_key=dedupe_key)
        return True

    def has_open_proposal(self, user, dedupe_key: str) -> bool:
        """同一用户同一去重键是否已有未过期的待确认事项（过期的顺手标记为 expired）。"""
        from smart_assistant.models import AgentProposal

        pending = AgentProposal.objects.filter(user=user, dedupe_key=dedupe_key, status=AgentProposal.STATUS_PENDING)
        for proposal in pending:
            if proposal.expires_at > timezone.now():
                return True
            expire_proposal(proposal)
        return False

    def propose(self, user, *, kind, title, fields, preview, dedupe_key, expires_at=None, content=""):
        """创建待确认事项并通知当事人；已有同键待确认事项或配额用完时返回 None。"""
        from notifications.models import Notification
        from notifications.service import NotificationService
        from smart_assistant.models import AgentProposal

        now = timezone.now()
        expires_at = min(expires_at or now + PROPOSAL_TTL, now + PROPOSAL_TTL)
        if expires_at <= now:
            return None
        if self.has_open_proposal(user, dedupe_key):
            self.stats["skipped_duplicate"] += 1
            return None
        if not self._take_action():
            return None
        with transaction.atomic():
            proposal = AgentProposal.objects.create(
                profile=self.profile,
                run=self.run,
                user=user,
                kind=kind,
                title=title[:200],
                fields=fields,
                preview=preview,
                dedupe_key=dedupe_key[:200],
                expires_at=expires_at,
            )
            NotificationService.create(
                user=user,
                type="agent_notify",
                title=f"待确认：{title}"[:200],
                content=content or f"{self.profile.name}为你准备了一项操作，点击后在智能助手里确认或取消。",
                link=f"/smart-assistant?proposal={proposal.pk}",
                priority=Notification.PRIORITY_NORMAL,
                dedupe_key=f"agent_proposal:{proposal.pk}",
            )
            self.event("proposal.created", user=user, proposal_id=proposal.pk, kind=kind)
        self.stats["proposals"] += 1
        return proposal

    def llm(self, system_prompt: str, prompt: str, *, purpose: str) -> str | None:
        """在配额内调用 LLM；配额为 0 表示不使用 LLM。超额或失败返回 None，调用方改用模板。"""
        quota = self.profile.daily_llm_quota
        if quota <= 0:
            return None
        if self._llm_used >= quota:
            if not self.llm_quota_hit:
                self.llm_quota_hit = True
                self.event("quota.exceeded", kind="llm", quota=quota)
            self.stats["llm_skipped_quota"] += 1
            return None
        from smart_assistant.extractors.llm_helpers import call_extractor_llm

        self._llm_used += 1
        self.stats["llm_calls"] += 1
        self.event("llm.call", purpose=purpose)
        text = call_extractor_llm(system_prompt, prompt)
        if not text or not text.strip():
            self.llm_fallbacks += 1
            self.event("llm.fallback", purpose=purpose, reason="error")
            return None
        return text.strip()


def expire_proposal(proposal) -> None:
    from smart_assistant.models import AgentProposal

    updated = AgentProposal.objects.filter(pk=proposal.pk, status=AgentProposal.STATUS_PENDING).update(
        status=AgentProposal.STATUS_EXPIRED, decided_at=timezone.now()
    )
    if updated:
        proposal.status = AgentProposal.STATUS_EXPIRED
        record_event(proposal.profile, "proposal.expired", user=proposal.user, proposal_id=proposal.pk)


def get_runner_class(key: str):
    path = RUNNERS.get(key)
    return import_string(path) if path else None


def _finish(run, status: str, *, stats=None, error: str = ""):
    run.status = status
    run.finished_at = timezone.now()
    run.stats = dict(stats or {})
    run.error = error[:500]
    run.save(update_fields=["status", "finished_at", "stats", "error"])
    return run


def _skip(profile, trigger, triggered_by, reason: str):
    from smart_assistant.models import AgentRun

    run = AgentRun.objects.create(profile=profile, trigger=trigger, triggered_by=triggered_by)
    record_event(profile, "run.skipped", run=run, reason=reason)
    return _finish(run, AgentRun.STATUS_SKIPPED, stats={"reason": reason})


def run_profile(key: str, trigger: str = "beat", triggered_by=None, today=None):
    """执行一次角色运行，返回 ``AgentRun``；角色不存在返回 None。"""
    from smart_assistant.models import AgentProfile, AgentRun

    with transaction.atomic():
        profile = AgentProfile.objects.select_for_update().filter(key=key).first()
        if profile is None:
            logger.warning("数字员工不存在: key=%s", key)
            return None
        runner_cls = get_runner_class(key)
        if not profile.enabled:
            return _skip(profile, trigger, triggered_by, "disabled")
        if runner_cls is None:
            return _skip(profile, trigger, triggered_by, "no_runner")
        running = AgentRun.objects.filter(
            profile=profile, status=AgentRun.STATUS_RUNNING, started_at__gte=timezone.now() - STALE_RUN_AFTER
        )
        if running.exists():
            return _skip(profile, trigger, triggered_by, "already_running")
        run = AgentRun.objects.create(profile=profile, trigger=trigger, triggered_by=triggered_by)
        record_event(profile, "run.started", run=run, trigger=trigger)

    ctx = RunContext(profile, run, today=today)
    try:
        runner_cls(ctx).run()
    except Exception as exc:
        logger.exception("数字员工运行失败: key=%s run=%s", key, run.pk)
        ctx.event("run.failed", error=type(exc).__name__)
        return _finish(run, AgentRun.STATUS_FAILED, stats=ctx.stats, error=f"{type(exc).__name__}: {exc}")
    status = AgentRun.STATUS_DEGRADED if ctx.degraded else AgentRun.STATUS_SUCCEEDED
    ctx.event("run.completed", status=status, **{k: int(v) for k, v in ctx.stats.items()})
    return _finish(run, status, stats=ctx.stats)
