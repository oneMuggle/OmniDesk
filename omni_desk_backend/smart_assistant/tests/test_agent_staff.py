"""S4-1 数字员工：框架、三个角色、待确认事项与管理端接口。"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from compliance.models import ComplianceIssue
from events.models import Schedule, ScheduleSwapRequest, TimeSlot, Trial
from meeting_rooms.models import MeetingRoom, MeetingRoomBooking
from memos.models import Memo
from notifications.models import Notification
from personnel.models import Personnel
from projects.models import Project
from smart_assistant.models import AgentProfile, AgentProposal, AgentRun, AgentRunEvent, AgentWriteLog
from smart_assistant.staff import proposals as proposal_service
from smart_assistant.staff.runtime import RunContext, day_start, run_profile
from smart_assistant.tasks import expire_agent_proposals, send_daily_digests, send_single_digest

API = "/api/smart-assistant"
LLM = "smart_assistant.extractors.llm_helpers.call_extractor_llm"


def make_user(username, **extra):
    return get_user_model().objects.create_user(username=username, password="x", **extra)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def profile(key, **changes):
    obj = AgentProfile.objects.get(key=key)
    for field, value in changes.items():
        setattr(obj, field, value)
    obj.save()
    return obj


def digest_of(user):
    return Notification.objects.get(user=user, title__startswith="智能助手每日晨报")


def events(key, event_type=None):
    qs = AgentRunEvent.objects.filter(profile__key=key)
    return qs.filter(event_type=event_type) if event_type else qs


@pytest.fixture
def admin(db):
    user = make_user("staff-admin", is_staff=True)
    user.groups.add(Group.objects.get_or_create(name="Admin")[0])
    return user


# ---------------------------------------------------------------------------
# 迁移与配置
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSeedAndBeat:
    def test_seeded_profiles_and_defaults(self):
        rows = {p.key: p for p in AgentProfile.objects.all()}
        assert set(rows) == {"secretary", "scheduler", "compliance"}
        assert rows["secretary"].enabled is True
        assert rows["scheduler"].enabled is False
        assert rows["compliance"].enabled is False

    def test_beat_entries(self):
        beat = django_settings.CELERY_BEAT_SCHEDULE
        assert beat["smart-assistant-daily-digest"]["task"] == "smart_assistant.tasks.send_daily_digests"
        assert beat["agent-scheduler-patrol"]["args"] == ("scheduler",)
        assert beat["agent-compliance-patrol"]["args"] == ("compliance",)
        assert beat["agent-proposals-expire"]["task"] == "smart_assistant.tasks.expire_agent_proposals"


# ---------------------------------------------------------------------------
# 框架
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRuntime:
    def test_disabled_profile_is_skipped_and_audited(self):
        run = run_profile("scheduler")
        assert run.status == AgentRun.STATUS_SKIPPED
        assert run.stats == {"reason": "disabled"}
        assert events("scheduler", "run.skipped").count() == 1

    def test_unknown_profile_returns_none(self):
        assert run_profile("nobody") is None

    def test_concurrent_run_is_skipped(self):
        p = profile("scheduler", enabled=True)
        AgentRun.objects.create(profile=p, status=AgentRun.STATUS_RUNNING)
        run = run_profile("scheduler")
        assert run.status == AgentRun.STATUS_SKIPPED
        assert run.stats["reason"] == "already_running"

    def test_stale_running_run_does_not_block(self):
        p = profile("scheduler", enabled=True)
        stale = AgentRun.objects.create(profile=p, status=AgentRun.STATUS_RUNNING)
        AgentRun.objects.filter(pk=stale.pk).update(started_at=timezone.now() - timedelta(hours=2))
        assert run_profile("scheduler").status == AgentRun.STATUS_SUCCEEDED

    def test_runner_exception_is_recorded_as_failed(self):
        profile("scheduler", enabled=True)
        with patch("smart_assistant.staff.roles.scheduler.SchedulerRunner.run", side_effect=RuntimeError("boom")):
            run = run_profile("scheduler")
        assert run.status == AgentRun.STATUS_FAILED
        assert "boom" in run.error
        assert events("scheduler", "run.failed").count() == 1

    def test_action_quota_exceeded_degrades_and_notifies_owner_once(self, admin):
        profile("secretary", daily_action_quota=2, owner=admin)
        for i in range(3):
            make_user(f"digest-{i}", is_staff=True)
        run = run_profile("secretary")
        assert run.status == AgentRun.STATUS_DEGRADED
        # admin 本人也是 staff：共 4 个目标用户，只发了 2 条晨报
        assert Notification.objects.filter(title__startswith="智能助手每日晨报").count() == 2
        assert events("secretary", "quota.exceeded").count() == 1
        assert run.stats["skipped_quota"] == 2
        owner_notes = Notification.objects.filter(user=admin, title__contains="动作配额已用完")
        assert owner_notes.count() == 1

    def test_quota_counts_across_runs_same_day(self):
        profile("secretary", daily_action_quota=1)
        make_user("d1", is_staff=True)
        make_user("d2", is_staff=True)
        run_profile("secretary")
        Notification.objects.all().delete()
        run = run_profile("secretary")
        assert run.status == AgentRun.STATUS_DEGRADED
        assert Notification.objects.filter(title__startswith="智能助手每日晨报").count() == 0

    def test_llm_quota_zero_means_no_llm(self):
        ctx = RunContext(profile("compliance", daily_llm_quota=0))
        with patch(LLM) as llm:
            assert ctx.llm("s", "p", purpose="t") is None
        llm.assert_not_called()
        assert not ctx.degraded

    def test_llm_quota_exceeded_and_failure_fallback(self):
        ctx = RunContext(profile("compliance", daily_llm_quota=2))
        with patch(LLM, side_effect=["ok", None]) as llm:
            assert ctx.llm("s", "p", purpose="t") == "ok"
            assert ctx.llm("s", "p", purpose="t") is None  # 调用失败 → 降级
            assert ctx.llm("s", "p", purpose="t") is None  # 超出配额 → 不再调用
        assert llm.call_count == 2
        assert events("compliance", "llm.call").count() == 2
        assert events("compliance", "llm.fallback").count() == 1
        assert events("compliance", "quota.exceeded").get().payload == {"kind": "llm", "quota": 2}
        assert ctx.degraded


# ---------------------------------------------------------------------------
# 个人秘书
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSecretary:
    def _setup(self):
        today = timezone.localdate()
        me = Personnel.objects.create(name="王五")
        other = Personnel.objects.create(name="赵六")
        user = make_user("brief-user", is_staff=True, personnel=me)
        Memo.objects.create(user=user, title="交周报", reminder_time=day_start(today) + timedelta(hours=10))
        Memo.objects.create(user=user, title="明天的事", reminder_time=day_start(today) + timedelta(days=1, hours=10))
        Schedule.objects.create(duty_date=today, duty_person=me)
        tomorrow = Schedule.objects.create(duty_date=today + timedelta(days=1), duty_leader=me)
        room = MeetingRoom.objects.create(name="一号会议室")
        MeetingRoomBooking.objects.create(
            meeting_room=room,
            user=user,
            title="评审会",
            start_time=day_start(today) + timedelta(hours=14),
            end_time=day_start(today) + timedelta(hours=15),
        )
        other_schedule = Schedule.objects.create(duty_date=today + timedelta(days=3), duty_person=other)
        ScheduleSwapRequest.objects.create(
            requester=other,
            original_schedule=other_schedule,
            target_personnel=me,
            reason="家里有事",
            expires_at=timezone.now() + timedelta(hours=48),
        )
        return user, tomorrow

    def test_digest_content_and_legacy_dedupe_key(self):
        user, _ = self._setup()
        result = send_daily_digests()
        assert result["status"] == AgentRun.STATUS_SUCCEEDED
        note = digest_of(user)
        today = timezone.localdate()
        assert note.type == "system"
        assert note.title == f"智能助手每日晨报（{today.isoformat()}）"
        assert note.dedupe_key == f"smart_assistant_daily_digest:{today.isoformat()}"
        assert note.link == "/smart-assistant"
        assert "交周报" in note.content and "明天的事" not in note.content
        assert "今天" in note.content and "值班人员" in note.content and "值班领导" in note.content
        assert "一号会议室 · 评审会" in note.content
        assert "赵六 申请与你换" in note.content and "家里有事" in note.content

    def test_rerun_same_day_does_not_duplicate(self):
        user, _ = self._setup()
        send_daily_digests()
        send_daily_digests()
        assert Notification.objects.filter(user=user, title__startswith="智能助手每日晨报").count() == 1
        assert "[追加]" not in digest_of(user).content

    def test_only_active_staff_receive(self):
        make_user("plain")
        make_user("gone", is_staff=True, is_active=False)
        staff = make_user("staffer", is_staff=True)
        send_daily_digests()
        assert list(Notification.objects.values_list("user", flat=True)) == [staff.pk]
        assert "今天没有需要特别关注的事项" in Notification.objects.get().content

    def test_disabled_secretary_sends_nothing(self):
        profile("secretary", enabled=False)
        make_user("staffer", is_staff=True)
        assert send_daily_digests()["status"] == AgentRun.STATUS_SKIPPED
        assert not Notification.objects.exists()

    def test_llm_tip_within_quota(self):
        user, _ = self._setup()
        profile("secretary", daily_llm_quota=5)
        with patch(LLM, return_value="记得下午两点评审会\n多余的第二行"):
            send_daily_digests()
        content = digest_of(user).content
        assert "> 记得下午两点评审会" in content and "多余的第二行" not in content

    def test_send_single_digest_legacy_task(self):
        user, _ = self._setup()
        assert send_single_digest(user.pk) == {"user_id": user.pk, "success": True}
        assert send_single_digest(999999)["reason"] == "user_not_found"
        profile("secretary", enabled=False)
        assert send_single_digest(user.pk)["reason"] == "disabled"


# ---------------------------------------------------------------------------
# 排班管理员
# ---------------------------------------------------------------------------


def add_trial(person, day, status="planned", title="振动试验"):
    trial = Trial.objects.create(title=title, client="客户", description="-", status=status)
    trial.responsible_persons.add(person)
    TimeSlot.objects.create(
        trial=trial, start_time=day_start(day) + timedelta(hours=9), end_time=day_start(day) + timedelta(hours=17)
    )
    return trial


@pytest.fixture
def duty(db):
    """两天后值班的张三，当天负责一个试验。"""
    day = timezone.localdate() + timedelta(days=2)
    person = Personnel.objects.create(name="张三")
    user = make_user("zhangsan", personnel=person)
    schedule = Schedule.objects.create(duty_date=day, duty_person=person)
    add_trial(person, day)
    profile("scheduler", enabled=True)
    return {"day": day, "person": person, "user": user, "schedule": schedule}


def person_with_account(name):
    person = Personnel.objects.create(name=name)
    make_user(f"u-{name}", personnel=person)
    return person


@pytest.mark.django_db
class TestScheduler:
    def test_trial_conflict_creates_proposal_with_best_candidate(self, duty):
        busy_neighbor = person_with_account("前一天值班")
        Schedule.objects.create(duty_date=duty["day"] - timedelta(days=1), duty_person=busy_neighbor)
        in_trial = person_with_account("也在试验")
        add_trial(in_trial, duty["day"], status="in_progress")
        Personnel.objects.create(name="无账号")
        Personnel.objects.create(name="已离职", status="inactive")
        heavy = person_with_account("值班多")
        for offset in (5, 6):
            Schedule.objects.create(duty_date=timezone.localdate() + timedelta(days=offset), duty_person=heavy)
        best = person_with_account("最闲")

        run = run_profile("scheduler")
        assert run.status == AgentRun.STATUS_SUCCEEDED
        proposal = AgentProposal.objects.get()
        assert proposal.user == duty["user"]
        assert proposal.kind == "swap_request"
        assert proposal.fields["target_personnel_id"] == best.pk
        assert proposal.expires_at <= day_start(duty["day"])
        assert proposal.preview["changes"][0]["after"] == "最闲"
        note = Notification.objects.get(user=duty["user"], type="agent_notify")
        assert note.link == f"/smart-assistant?proposal={proposal.pk}"
        assert events("scheduler", "proposal.created").count() == 1

    def test_second_run_does_not_duplicate(self, duty):
        person_with_account("接替人")
        run_profile("scheduler")
        run_profile("scheduler")
        assert AgentProposal.objects.count() == 1

    def test_completed_trial_is_not_a_conflict(self, duty):
        Trial.objects.update(status="completed")
        person_with_account("接替人")
        run_profile("scheduler")
        assert not AgentProposal.objects.exists()

    def test_no_candidate_only_notifies(self, duty):
        run_profile("scheduler")
        assert not AgentProposal.objects.exists()
        assert "没有找到合适的接替人" in Notification.objects.get(user=duty["user"], type="agent_notify").content

    def test_approve_creates_swap_request(self, duty):
        target = person_with_account("接替人")
        run_profile("scheduler")
        proposal = AgentProposal.objects.get()
        resp = client_for(duty["user"]).post(f"{API}/proposals/{proposal.pk}/approve/")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["confirmed"] is True and body["reversible"] is False
        swap = ScheduleSwapRequest.objects.get()
        assert swap.requester == duty["person"] and swap.target_personnel == target
        assert swap.original_schedule == duty["schedule"]
        proposal.refresh_from_db()
        assert proposal.status == AgentProposal.STATUS_APPROVED
        assert events("scheduler", "proposal.approved").count() == 1

    def test_approve_after_schedule_changed_conflicts(self, duty):
        person_with_account("接替人")
        run_profile("scheduler")
        proposal = AgentProposal.objects.get()
        Schedule.objects.filter(pk=duty["schedule"].pk).update(duty_person=Personnel.objects.create(name="新人"))
        resp = client_for(duty["user"]).post(f"{API}/proposals/{proposal.pk}/approve/")
        assert resp.status_code == 409
        assert resp.json()["code"] == "conflict"
        proposal.refresh_from_db()
        assert proposal.status == AgentProposal.STATUS_FAILED
        assert not ScheduleSwapRequest.objects.exists()
        assert events("scheduler", "proposal.failed").count() == 1

    def test_inactive_and_same_person_notify_owner(self, admin):
        owner = make_user("排班负责人")
        profile("scheduler", enabled=True, owner=owner)
        day = timezone.localdate() + timedelta(days=1)
        gone = Personnel.objects.create(name="离职者", status="inactive")
        Schedule.objects.create(duty_date=day, duty_person=gone)
        both = Personnel.objects.create(name="兼任者")
        Schedule.objects.create(duty_date=day + timedelta(days=1), duty_person=both, duty_leader=both)
        run = run_profile("scheduler")
        titles = list(Notification.objects.filter(user=owner).values_list("title", flat=True))
        assert any("已离职" in t for t in titles)
        assert any("同一人" in t for t in titles)
        assert not Notification.objects.filter(user=admin).exists()
        assert run.stats["conflict_inactive"] == 1 and run.stats["conflict_same_person"] == 1

    def test_without_owner_admins_are_notified(self, admin):
        profile("scheduler", enabled=True)
        gone = Personnel.objects.create(name="离职者", status="inactive")
        Schedule.objects.create(duty_date=timezone.localdate() + timedelta(days=1), duty_person=gone)
        run_profile("scheduler")
        assert Notification.objects.filter(user=admin, title__contains="已离职").exists()

    def test_schedules_outside_horizon_are_ignored(self, db):
        profile("scheduler", enabled=True)
        gone = Personnel.objects.create(name="离职者", status="inactive")
        Schedule.objects.create(duty_date=timezone.localdate() + timedelta(days=8), duty_person=gone)
        run = run_profile("scheduler")
        assert run.stats.get("conflict_inactive", 0) == 0


# ---------------------------------------------------------------------------
# 合规专员
# ---------------------------------------------------------------------------


@pytest.fixture
def compliance_setup(db):
    today = timezone.localdate()
    manager = make_user("项目经理")
    project = Project.objects.create(name="S4 项目", manager=manager)
    overdue = ComplianceIssue.objects.create(
        project=project,
        issue_type="内容缺失",
        description="原始记录缺少签名",
        status="处理中",
        due_date=today - timedelta(days=2),
    )
    soon = ComplianceIssue.objects.create(
        project=project, issue_type="其他", description="封面页码", status="待处理", due_date=today + timedelta(days=2)
    )
    ComplianceIssue.objects.create(
        project=project, issue_type="其他", description="很久以后", status="待处理", due_date=today + timedelta(days=10)
    )
    ComplianceIssue.objects.create(
        project=project, issue_type="其他", description="已解决", status="已解决", due_date=today - timedelta(days=1)
    )
    profile("compliance", enabled=True)
    return {"manager": manager, "overdue": overdue, "soon": soon}


@pytest.mark.django_db
class TestCompliance:
    def test_digest_and_llm_suggestion(self, compliance_setup):
        manager = compliance_setup["manager"]
        with patch(LLM, return_value="- 补签原始记录\n- 复核后归档"):
            run = run_profile("compliance")
        assert run.status == AgentRun.STATUS_SUCCEEDED
        digest = Notification.objects.get(user=manager, title__startswith="合规提醒")
        assert "2 个问题" in digest.title
        assert "已逾期 2 天" in digest.content and "2 天后到期" in digest.content
        assert "很久以后" not in digest.content and "已解决" not in digest.content
        proposal = AgentProposal.objects.get()
        assert proposal.kind == "compliance_suggestion"
        assert proposal.fields["issue_id"] == compliance_setup["overdue"].pk
        assert proposal.fields["source"] == "llm"
        assert "补签原始记录" in proposal.preview["items"][0]

    def test_llm_quota_exhausted_uses_template(self, compliance_setup):
        profile("compliance", daily_llm_quota=0)
        run_profile("compliance")
        proposal = AgentProposal.objects.get()
        assert proposal.fields["source"] == "template"
        assert "补录" in proposal.fields["suggestion"]

    def test_llm_failure_degrades_run(self, compliance_setup):
        with patch(LLM, return_value=None):
            run = run_profile("compliance")
        assert run.status == AgentRun.STATUS_DEGRADED
        assert AgentProposal.objects.get().fields["source"] == "template"

    def test_approve_saves_memo_and_can_revert(self, compliance_setup):
        manager = compliance_setup["manager"]
        with patch(LLM, return_value="- 补签原始记录"):
            run_profile("compliance")
        proposal = AgentProposal.objects.get()
        resp = client_for(manager).post(f"{API}/proposals/{proposal.pk}/approve/")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["reversible"] is True
        memo = Memo.objects.get(user=manager)
        assert memo.title == "整改：S4 项目 · 内容缺失"
        assert "补签原始记录" in memo.content
        assert memo.reminder_time is None  # 已逾期不设提醒
        log = AgentWriteLog.objects.get(pk=body["write_log_id"])
        assert log.target_model == "memos.Memo" and log.operation == "create"
        revert = client_for(manager).post(f"{API}/write-logs/{log.pk}/revert/")
        assert revert.status_code == 200, revert.content
        assert not Memo.objects.filter(pk=memo.pk).exists()

    def test_approve_after_issue_resolved_conflicts(self, compliance_setup):
        run_profile("compliance")
        proposal = AgentProposal.objects.get()
        ComplianceIssue.objects.filter(pk=compliance_setup["overdue"].pk).update(status="已解决")
        resp = client_for(compliance_setup["manager"]).post(f"{API}/proposals/{proposal.pk}/approve/")
        assert resp.status_code == 409
        assert not Memo.objects.exists()

    def test_rejected_suggestion_not_reproposed(self, compliance_setup):
        run_profile("compliance")
        proposal = AgentProposal.objects.get()
        assert client_for(compliance_setup["manager"]).post(f"{API}/proposals/{proposal.pk}/reject/").status_code == 200
        with patch(LLM) as llm:
            run_profile("compliance")
        assert AgentProposal.objects.count() == 1
        llm.assert_not_called()


# ---------------------------------------------------------------------------
# 待确认事项接口
# ---------------------------------------------------------------------------


@pytest.fixture
def proposal(db):
    owner = make_user("proposal-owner")
    p = AgentProposal.objects.create(
        profile=AgentProfile.objects.get(key="compliance"),
        user=owner,
        kind="compliance_suggestion",
        title="测试事项",
        fields={"issue_id": 0, "secret": "内部字段"},
        preview={"action": "保存整改建议", "target": {"type": "合规问题", "label": "X"}, "changes": []},
        dedupe_key="k",
        expires_at=timezone.now() + timedelta(hours=1),
    )
    return p


@pytest.mark.django_db
class TestProposalApi:
    def test_list_and_detail_only_own_without_internal_fields(self, proposal):
        owner = proposal.user
        resp = client_for(owner).get(f"{API}/proposals/?status=pending")
        assert resp.status_code == 200
        rows = resp.json()["results"] if isinstance(resp.json(), dict) else resp.json()
        assert [r["id"] for r in rows] == [proposal.pk]
        detail = client_for(owner).get(f"{API}/proposals/{proposal.pk}/").json()
        assert "fields" not in detail and "内部字段" not in str(detail)
        assert detail["summary"].startswith("待确认：保存整改建议")
        stranger = make_user("stranger")
        assert client_for(stranger).get(f"{API}/proposals/{proposal.pk}/").status_code == 404
        assert client_for(stranger).post(f"{API}/proposals/{proposal.pk}/approve/").status_code == 404
        assert client_for(stranger).post(f"{API}/proposals/{proposal.pk}/reject/").status_code == 404

    def test_reject_then_second_decision_409(self, proposal):
        c = client_for(proposal.user)
        resp = c.post(f"{API}/proposals/{proposal.pk}/reject/")
        assert resp.status_code == 200 and resp.json()["proposal"]["status"] == "rejected"
        assert c.post(f"{API}/proposals/{proposal.pk}/approve/").status_code == 409
        assert c.post(f"{API}/proposals/{proposal.pk}/reject/").status_code == 409
        assert events("compliance", "proposal.rejected").count() == 1

    def test_expired_returns_410(self, proposal):
        AgentProposal.objects.filter(pk=proposal.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        resp = client_for(proposal.user).post(f"{API}/proposals/{proposal.pk}/approve/")
        assert resp.status_code == 410 and resp.json()["code"] == "expired"
        proposal.refresh_from_db()
        assert proposal.status == AgentProposal.STATUS_EXPIRED

    def test_unknown_kind_fails(self, proposal):
        AgentProposal.objects.filter(pk=proposal.pk).update(kind="nope")
        assert client_for(proposal.user).post(f"{API}/proposals/{proposal.pk}/approve/").status_code == 409

    def test_expire_task(self, proposal):
        AgentProposal.objects.filter(pk=proposal.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        assert expire_agent_proposals() == {"expired": 1}
        proposal.refresh_from_db()
        assert proposal.status == AgentProposal.STATUS_EXPIRED
        assert events("compliance", "proposal.expired").count() == 1
        assert proposal_service.expire_stale() == 0

    def test_requires_login(self, proposal):
        assert APIClient().get(f"{API}/proposals/").status_code in (401, 403)


# ---------------------------------------------------------------------------
# 管理端接口
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestProfileAdminApi:
    def test_non_admin_forbidden(self):
        staff = make_user("just-staff", is_staff=True)
        assert client_for(staff).get(f"{API}/agent-profiles/").status_code == 403
        assert client_for(staff).patch(f"{API}/agent-profiles/scheduler/", {"enabled": True}).status_code == 403

    def test_list_includes_usage_and_last_run(self, admin):
        run_profile("scheduler")
        resp = client_for(admin).get(f"{API}/agent-profiles/")
        assert resp.status_code == 200
        rows = resp.json()["results"] if isinstance(resp.json(), dict) else resp.json()
        by_key = {r["key"]: r for r in rows}
        assert set(by_key) == {"secretary", "scheduler", "compliance"}
        assert by_key["scheduler"]["usage_today"] == {"actions": 0, "llm_calls": 0}
        assert by_key["scheduler"]["last_run"]["status"] == "skipped"
        assert "system_prompt" not in by_key["scheduler"]

    def test_patch_toggles_and_audits(self, admin):
        c = client_for(admin)
        resp = c.patch(
            f"{API}/agent-profiles/scheduler/",
            {"enabled": True, "daily_action_quota": 5, "owner": admin.pk},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        p = AgentProfile.objects.get(key="scheduler")
        assert p.enabled and p.daily_action_quota == 5 and p.owner == admin
        change = events("scheduler", "config.changed").get()
        assert change.user == admin
        assert change.payload["changes"]["enabled"] == {"before": False, "after": True}

    def test_patch_rejects_readonly_and_invalid(self, admin):
        c = client_for(admin)
        resp = c.patch(f"{API}/agent-profiles/scheduler/", {"name": "改名"}, format="json")
        assert resp.status_code == 400 and resp.json()["code"] == "readonly_field"
        assert c.patch(f"{API}/agent-profiles/scheduler/", {"daily_llm_quota": -1}, format="json").status_code == 400
        assert AgentProfile.objects.get(key="scheduler").name == "排班管理员"

    def test_run_now(self, admin):
        c = client_for(admin)
        assert c.post(f"{API}/agent-profiles/scheduler/run/").status_code == 409
        profile("scheduler", enabled=True)
        with patch("smart_assistant.tasks.run_agent_profile.delay") as delay:
            assert c.post(f"{API}/agent-profiles/scheduler/run/").status_code == 202
        delay.assert_called_once_with("scheduler", "manual", admin.pk)

    def test_runs_with_events(self, admin):
        profile("scheduler", enabled=True)
        run_profile("scheduler", "manual", triggered_by=admin)
        resp = client_for(admin).get(f"{API}/agent-profiles/scheduler/runs/")
        assert resp.status_code == 200
        run = resp.json()[0]
        assert run["trigger"] == "manual" and run["status"] == "succeeded"
        assert [e["event_type"] for e in run["events"]] == ["run.started", "run.completed"]
