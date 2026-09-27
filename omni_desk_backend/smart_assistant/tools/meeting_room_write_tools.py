"""会议室预约与取消（S3-1 写工具）。

- 预约：与页面一致，所有登录用户可预约；确认时锁住会议室行，再走模型自带的冲突检查
  （已有预约、维护时段、开始时间不能早于现在），冲突返回 ``booking_conflict``（409）。
- 取消：AI **只能取消本人**、未开始的预约（即使是管理员）；按 ``updated_at`` 做版本校验。
- 撤销：预约 → 删除本次创建的预约（创建后未被修改）；取消 → 原时段仍空闲且未开始时重建预约。
"""

from __future__ import annotations

from datetime import date as date_cls
from datetime import timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from meeting_rooms.models import MeetingRoom, MeetingRoomBooking, MeetingRoomMaintenance

from ..writes.preview import build_preview, change
from ..writes.write_log import record_write
from .write_base import STALE_MESSAGE, ConfirmedWriteTool, fmt_dt, parse_local_datetime

TARGET_MODEL = "meeting_rooms.MeetingRoomBooking"
DEFAULT_TITLE = "会议"


def _utc_iso(value) -> str:
    """统一转成 UTC 再序列化：内存对象带本地时区、数据库读回是 UTC，直接比较会误判。"""
    return value.astimezone(dt_timezone.utc).isoformat()


def booking_snapshot(booking: MeetingRoomBooking) -> dict:
    return {
        "meeting_room_id": booking.meeting_room_id,
        "user_id": booking.user_id,
        "start_time": _utc_iso(booking.start_time),
        "end_time": _utc_iso(booking.end_time),
        "title": booking.title,
        "participants": booking.participants or "",
        "description": booking.description or "",
    }


def booking_label(room_name: str, start, end) -> str:
    return f"{room_name} · {fmt_dt(start)}–{timezone.localtime(end).strftime('%H:%M')}"


def _validation_message(exc: ValidationError) -> str:
    messages = getattr(exc, "messages", None) or [str(exc)]
    return "；".join(str(m) for m in messages)[:200]


def _find_room(name: str):
    """按名称找会议室：先精确，再包含；返回 (room, error_message)。"""
    name = (name or "").strip()
    if not name:
        names = "、".join(MeetingRoom.objects.order_by("name").values_list("name", flat=True)[:10])
        return None, f"请说明要预约哪个会议室（可选：{names or '暂无会议室'}）"
    exact = MeetingRoom.objects.filter(name__iexact=name).first()
    if exact:
        return exact, None
    matches = list(MeetingRoom.objects.filter(name__icontains=name).order_by("name")[:6])
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        names = "、".join(MeetingRoom.objects.order_by("name").values_list("name", flat=True)[:10])
        return None, f"没有找到名为「{name}」的会议室（可选：{names or '暂无会议室'}）"
    return None, "匹配到多个会议室：" + "、".join(m.name for m in matches[:5]) + "，请说完整名称"


class MeetingRoomBookTool(ConfirmedWriteTool):
    name = "meeting_room_book"
    intent_type = "meeting_room_book"
    description = "预约会议室（写操作，需要确认；会检查时段冲突和维护安排）"
    TASK_LABEL = "预约会议室"
    FIELDS = {
        "room": "会议室名称",
        "start_time": "开始时间",
        "end_time": "结束时间（用户只说了时长时，按开始时间加时长推算）",
        "title": "会议主题（可为 null）",
        "participants": "参会人员（可为 null）",
    }

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return cls.build_schema(
            "预约会议室（写操作，需要用户确认；会检查时段冲突和维护安排，可撤销）。"
            "示例：'帮我订明天下午2点到3点的3楼大会议室，开项目周会'。",
            {
                "room": {"type": "string", "description": "会议室名称"},
                "start_time": {"type": "string", "description": "开始时间，YYYY-MM-DDTHH:MM"},
                "end_time": {"type": "string", "description": "结束时间，YYYY-MM-DDTHH:MM"},
                "title": {"type": "string", "description": "会议主题"},
                "participants": {"type": "string", "description": "参会人员"},
            },
        )

    def dry_run(self, user, params, ctx):
        room, error = _find_room(params.get("room") if isinstance(params.get("room"), str) else "")
        if error:
            return self.fail(error)
        start = parse_local_datetime(params.get("start_time"))
        end = parse_local_datetime(params.get("end_time"))
        if start is None or end is None:
            return self.fail("请说明预约的开始和结束时间")
        if end <= start:
            return self.fail("结束时间必须晚于开始时间")
        if start < timezone.now():
            return self.fail("预约时间不能早于现在")
        busy = (
            MeetingRoomBooking.objects.filter(meeting_room=room, start_time__lt=end, end_time__gt=start)
            .order_by("start_time")
            .first()
        )
        if busy:
            return self.fail(
                f"{room.name} 在 {fmt_dt(busy.start_time)}–{timezone.localtime(busy.end_time).strftime('%H:%M')} 已被预约，请换个时段或会议室",
                code="booking_conflict",
            )
        if MeetingRoomMaintenance.objects.filter(meeting_room=room, start_time__lt=end, end_time__gt=start).exists():
            return self.fail(f"{room.name} 在该时段安排了维护，请换个时段或会议室", code="booking_conflict")
        title = (params.get("title") or "").strip()[:255] if isinstance(params.get("title"), str) else ""
        participants = params.get("participants") if isinstance(params.get("participants"), str) else ""
        title = title or DEFAULT_TITLE
        preview = build_preview(
            action="预约会议室",
            target_type="会议室预约",
            target_label=booking_label(room.name, start, end),
            changes=[
                change("meeting_room", "会议室", None, room.name),
                change("time", "时间", None, f"{fmt_dt(start)}–{timezone.localtime(end).strftime('%H:%M')}"),
                change("title", "主题", None, title),
                change("participants", "参会人员", None, participants or "—"),
            ],
            affected_label="条预约",
            permission_source="登录用户均可预约",
        )
        return self.draft(
            preview,
            {
                "room_id": room.pk,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "title": title,
                "participants": participants.strip(),
            },
        )

    def confirm(self, user, fields, ctx):
        start = parse_local_datetime(fields.get("start_time"))
        end = parse_local_datetime(fields.get("end_time"))
        if start is None or end is None:
            return self.fail("确认内容缺失，请重新发起", code="stale_confirmation")
        with transaction.atomic():
            # 锁住会议室行：同一会议室的 AI 预约串行执行，冲突检查不会被并发绕过
            room = MeetingRoom.objects.select_for_update().filter(pk=fields.get("room_id")).first()
            if room is None:
                return self.fail("会议室已不存在，请重新发起", code="stale_confirmation")
            booking = MeetingRoomBooking(
                meeting_room=room,
                user=user,
                start_time=start,
                end_time=end,
                title=(fields.get("title") or DEFAULT_TITLE)[:255],
                participants=fields.get("participants") or "",
            )
            try:
                booking.save()  # save() 内部 full_clean()：冲突 / 维护 / 过去时间
            except ValidationError as exc:
                return self.fail(_validation_message(exc), code="booking_conflict")
            log = record_write(
                ctx,
                user,
                tool_name=self.intent_type,
                target_model=TARGET_MODEL,
                target_pk=booking.pk,
                operation="create",
                before=None,
                after=booking_snapshot(booking),
            )
        return self.done(
            f"已预约 {booking_label(room.name, start, end)}（{booking.title}）", log, booking_id=booking.pk
        )


class MeetingRoomCancelTool(ConfirmedWriteTool):
    name = "meeting_room_cancel"
    intent_type = "meeting_room_cancel"
    description = "取消我自己的、尚未开始的会议室预约（写操作，需要确认；原时段仍空闲时可撤销）"
    TASK_LABEL = "取消会议室预约"
    FIELDS = {
        "booking_id": "预约 ID（整数；用户没提时为 null）",
        "keyword": "预约主题或会议室名称中的关键词（可为 null）",
        "date": "预约日期 YYYY-MM-DD（可为 null）",
    }

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return cls.build_schema(
            "取消当前用户本人的、尚未开始的会议室预约（写操作，需要用户确认）。示例：'把我明天的周会预约取消'。",
            {
                "booking_id": {"type": "integer", "description": "预约 ID"},
                "keyword": {"type": "string", "description": "预约主题或会议室名称关键词"},
                "date": {"type": "string", "description": "预约日期 YYYY-MM-DD"},
            },
        )

    def dry_run(self, user, params, ctx):
        qs = MeetingRoomBooking.objects.filter(user=user, start_time__gt=timezone.now()).select_related("meeting_room")
        booking_id = params.get("booking_id")
        keyword = params.get("keyword").strip() if isinstance(params.get("keyword"), str) else ""
        day = None
        if isinstance(params.get("date"), str) and params["date"].strip():
            try:
                day = date_cls.fromisoformat(params["date"].strip()[:10])
            except ValueError:
                return self.fail(f"无法识别日期「{params['date']}」")
        if booking_id not in (None, ""):
            try:
                qs = qs.filter(pk=int(booking_id))
            except (TypeError, ValueError):
                return self.fail("预约 ID 应为数字")
        if keyword:
            qs = qs.filter(Q(title__icontains=keyword) | Q(meeting_room__name__icontains=keyword))
        if day is not None:
            qs = qs.filter(start_time__date=day)
        if booking_id in (None, "") and not keyword and day is None:
            return self.fail("请说明要取消哪一个预约（主题、会议室或日期）")
        rows = list(qs.order_by("start_time")[:6])
        if not rows:
            return self.fail("没有找到你名下尚未开始的匹配预约")
        if len(rows) > 1:
            listing = "；".join(
                f"#{b.pk} {booking_label(b.meeting_room.name, b.start_time, b.end_time)} {b.title}" for b in rows[:5]
            )
            return self.fail(f"找到多个匹配的预约：{listing}。请指明要取消哪一个")
        booking = rows[0]
        preview = build_preview(
            action="取消会议室预约",
            target_type="会议室预约",
            target_label=f"{booking_label(booking.meeting_room.name, booking.start_time, booking.end_time)} · {booking.title}",
            changes=[change("status", "预约", "有效", "已取消")],
            affected_label="条预约",
            permission_source="本人的预约",
        )
        return self.draft(preview, {"booking_id": booking.pk, "version": booking.updated_at.isoformat()})

    def confirm(self, user, fields, ctx):
        with transaction.atomic():
            booking = (
                MeetingRoomBooking.objects.select_for_update().filter(pk=fields.get("booking_id"), user=user).first()
            )
            if booking is None:
                return self.fail("预约不存在或已被取消", code="stale_confirmation")
            if fields.get("version") and booking.updated_at.isoformat() != fields["version"]:
                return self.fail(STALE_MESSAGE, code="stale_confirmation")
            if booking.start_time <= timezone.now():
                return self.fail("预约已经开始，不能再取消", code="state_conflict")
            before = booking_snapshot(booking)
            label = (
                f"{booking_label(booking.meeting_room.name, booking.start_time, booking.end_time)}（{booking.title}）"
            )
            booking_pk = booking.pk
            booking.delete()
            log = record_write(
                ctx,
                user,
                tool_name=self.intent_type,
                target_model=TARGET_MODEL,
                target_pk=booking_pk,
                operation="delete",
                before=before,
                after=None,
            )
        return self.done(f"已取消预约 {label}", log, booking_id=booking_pk)


class BookingRevertHandler:
    """撤销预约（删除）或撤销取消（在原时段重建预约）。"""

    def revert(self, log, user):
        from ..writes.revert import RevertConflict, RevertResult

        if log.operation == "create":
            booking = MeetingRoomBooking.objects.select_for_update().filter(pk=log.target_pk, user=user).first()
            if booking is None:
                raise RevertConflict("预约已不存在，无需撤销。")
            current = booking_snapshot(booking)
            if current != (log.after or {}):
                raise RevertConflict("预约创建后已被修改，无法安全撤销。", current=current)
            booking.delete()
            return RevertResult(operation="delete", before=current, after=None, target_pk=str(log.target_pk))
        if log.operation == "delete":
            snapshot = log.before or {}
            if snapshot.get("user_id") != user.pk:
                raise RevertConflict("只能恢复本人的预约。")
            start = parse_local_datetime(snapshot.get("start_time"))
            end = parse_local_datetime(snapshot.get("end_time"))
            if start is None or end is None or start <= timezone.now():
                raise RevertConflict("原预约时段已经开始或已过去，无法恢复。")
            room = MeetingRoom.objects.select_for_update().filter(pk=snapshot.get("meeting_room_id")).first()
            if room is None:
                raise RevertConflict("会议室已不存在，无法恢复预约。")
            booking = MeetingRoomBooking(
                meeting_room=room,
                user=user,
                start_time=start,
                end_time=end,
                title=snapshot.get("title") or DEFAULT_TITLE,
                participants=snapshot.get("participants") or "",
                description=snapshot.get("description") or "",
            )
            try:
                booking.save()
            except ValidationError as exc:
                raise RevertConflict(f"原时段已不可用，无法恢复预约：{_validation_message(exc)}") from exc
            return RevertResult(
                operation="create", before=None, after=booking_snapshot(booking), target_pk=str(booking.pk)
            )
        raise RevertConflict("该操作类型不支持回滚。")
