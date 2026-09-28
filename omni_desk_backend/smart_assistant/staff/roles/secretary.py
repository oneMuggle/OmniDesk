"""个人秘书：工作日晨报（S4-1，接替原 ``generate_daily_digest``）。

晨报内容直接从数据库汇总（备忘、值班、会议、待我处理的换班），不再每人跑一次
完整编排链路；LLM 只在配额内为每人写一句「今日提示」，配额为 0 或用完时省略。
通知标题与去重键沿用原晨报，切换当天不会重复推送。
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from observability import get_logger

from ..runtime import RoleRunner, day_start

logger = get_logger(__name__, "smart_assistant")

WEEKDAYS = "一二三四五六日"
MAX_ITEMS = 10


def digest_title(today) -> str:
    return f"智能助手每日晨报（{today.isoformat()}）"


def digest_dedupe_key(today) -> str:
    return f"smart_assistant_daily_digest:{today.isoformat()}"


def _local_hm(value) -> str:
    return timezone.localtime(value).strftime("%H:%M") if value else ""


def _personnel(user):
    try:
        return user.personnel
    except Exception:
        return None


def collect_brief(user, today) -> dict:
    """汇总某用户今天需要关注的事项（只读，只查本人数据）。"""
    from events.models import Schedule, ScheduleSwapRequest
    from meeting_rooms.models import MeetingRoomBooking
    from memos.models import Memo

    start, end = day_start(today), day_start(today + timedelta(days=1))
    memos = list(
        Memo.objects.filter(user=user, is_completed=False, reminder_time__gte=start, reminder_time__lt=end).order_by(
            "reminder_time"
        )[:MAX_ITEMS]
    )
    meetings = list(
        MeetingRoomBooking.objects.filter(user=user, start_time__gte=start, start_time__lt=end)
        .select_related("meeting_room")
        .order_by("start_time")[:MAX_ITEMS]
    )
    duties, swaps = [], []
    person = _personnel(user)
    if person is not None:
        for schedule in Schedule.objects.filter(duty_date__in=[today, today + timedelta(days=1)]).order_by("duty_date"):
            day = "今天" if schedule.duty_date == today else "明天"
            if schedule.duty_person_id == person.pk:
                duties.append(f"{day}（{schedule.duty_date:%m-%d}）值班人员")
            if schedule.duty_leader_id == person.pk:
                duties.append(f"{day}（{schedule.duty_date:%m-%d}）值班领导")
        swaps = list(
            ScheduleSwapRequest.objects.filter(target_personnel=person, status=ScheduleSwapRequest.STATUS_PENDING)
            .select_related("requester", "original_schedule")
            .order_by("created_at")[:MAX_ITEMS]
        )
    return {"memos": memos, "meetings": meetings, "duties": duties, "swaps": swaps}


def render_brief(today, data: dict, tip: str | None = None) -> str:
    lines = [f"## 今日概览（{today.isoformat()} 周{WEEKDAYS[today.weekday()]}）"]
    if tip:
        lines += ["", f"> {tip}"]

    def section(title, items):
        lines.extend(["", f"### {title}（{len(items)}）" if items else f"### {title}"])
        lines.extend(items or ["- 无"])

    section("备忘", [f"- {_local_hm(m.reminder_time)} {m.title}" for m in data["memos"]])
    section("值班", [f"- {d}" for d in data["duties"]])
    section(
        "会议",
        [
            f"- {_local_hm(b.start_time)}-{_local_hm(b.end_time)} {b.meeting_room.name} · {b.title}"
            for b in data["meetings"]
        ],
    )
    section(
        "待我处理的换班",
        [
            f"- {s.requester.name} 申请与你换 {s.original_schedule.duty_date:%m-%d} 的班"
            + (f"（{s.reason[:40]}）" if s.reason else "")
            for s in data["swaps"]
        ],
    )
    if not any(data.values()):
        lines += ["", "今天没有需要特别关注的事项。"]
    return "\n".join(lines)


def _facts_for_llm(today, data: dict) -> str:
    return (
        f"日期：{today.isoformat()}\n"
        f"今日备忘 {len(data['memos'])} 条：" + "；".join(m.title[:30] for m in data["memos"][:5]) + "\n"
        f"值班：" + ("；".join(data["duties"]) or "无") + "\n"
        f"今日会议 {len(data['meetings'])} 个：" + "；".join(b.title[:30] for b in data["meetings"][:5]) + "\n"
        f"待处理换班 {len(data['swaps'])} 条"
    )


class SecretaryRunner(RoleRunner):
    """给 ``is_active`` 且 ``is_staff`` 的用户推送晨报（与原晨报推送范围一致）。"""

    def target_users(self):
        User = get_user_model()
        return User.objects.filter(is_active=True, is_staff=True).order_by("id")

    def run(self):
        for user in self.target_users():
            self.ctx.stats["users"] += 1
            try:
                self.send_brief(user)
            except Exception:
                logger.exception("晨报生成失败: user=%s", user.pk)
                self.ctx.stats["errors"] += 1

    def send_brief(self, user) -> bool:
        today = self.ctx.today
        data = collect_brief(user, today)
        tip = None
        if any(data.values()):
            tip = self.ctx.llm(self.ctx.profile.system_prompt, _facts_for_llm(today, data), purpose="daily_brief_tip")
            tip = tip.splitlines()[0][:80] if tip else None
        return self.ctx.notify(
            user,
            type="system",
            title=digest_title(today),
            content=render_brief(today, data, tip),
            link="/smart-assistant",
            dedupe_key=digest_dedupe_key(today),
        )
