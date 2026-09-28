"""试验日程创建（S3-2 写工具）。

权限与页面接口一致（管理员 / HR）。确认卡片列出时间段、责任人、设备；与其他试验
在同一时段共用设备或责任人时给出**冲突提示但不阻止**（页面接口本身不检查冲突）。
撤销 = 删除仍未被修改的试验（时间段级联删除）。
"""

from __future__ import annotations

from datetime import timezone as dt_timezone
from itertools import pairwise

from django.db import transaction
from django.db.models import Q

from events.models import Equipment, TimeSlot, Trial
from personnel.models import Personnel

from ..writes.preview import build_preview, change
from ..writes.write_log import record_write
from .write_base import ConfirmedWriteTool, fmt_dt, parse_local_datetime, privileged_source

TARGET_MODEL = "events.Trial"
MAX_SLOTS = 10
MAX_NAMES = 20
MAX_CONFLICTS = 5
#: 已结束的试验不参与冲突提示
INACTIVE_STATUSES = ("cancelled", "completed")


def _utc_iso(value) -> str:
    return value.astimezone(dt_timezone.utc).isoformat()


def _names(value) -> list[str]:
    """姓名 / 设备名：接受列表或用逗号、顿号分隔的字符串；去重保序。"""
    if isinstance(value, str):
        for sep in ("，", "、", ";", "；"):
            value = value.replace(sep, ",")
        value = value.split(",")
    if not isinstance(value, list):
        return []
    seen: list[str] = []
    for item in value:
        name = item.strip() if isinstance(item, str) else ""
        if name and name not in seen:
            seen.append(name)
    return seen


def _raw_slots(params: dict) -> list[dict]:
    slots = params.get("time_slots")
    if isinstance(slots, dict):
        slots = [slots]
    if not isinstance(slots, list) or not slots:
        # 抽取模型只擅长扁平 JSON：也接受单段 start_time / end_time
        if params.get("start_time") or params.get("end_time"):
            slots = [{"start_time": params.get("start_time"), "end_time": params.get("end_time")}]
        else:
            slots = []
    return [slot for slot in slots if isinstance(slot, dict)]


def parse_slots(params: dict) -> tuple[list[dict] | None, str | None]:
    """返回 ``([{start, end, description}], None)`` 或 ``(None, 错误信息)``；按开始时间排序。"""
    raw = _raw_slots(params)
    if not raw:
        return None, "请提供试验时间（开始和结束时间）"
    if len(raw) > MAX_SLOTS:
        return None, f"一次最多创建 {MAX_SLOTS} 个时间段"
    slots = []
    for index, item in enumerate(raw, start=1):
        start = parse_local_datetime(item.get("start_time"))
        end = parse_local_datetime(item.get("end_time"))
        if start is None or end is None:
            return None, f"第 {index} 段时间格式不正确，请给出具体的开始和结束时间"
        if end <= start:
            return None, f"第 {index} 段结束时间必须晚于开始时间"
        desc = item.get("description") if isinstance(item.get("description"), str) else ""
        slots.append({"start": start, "end": end, "description": desc.strip()[:200]})
    slots.sort(key=lambda slot: slot["start"])
    for prev, nxt in pairwise(slots):
        if nxt["start"] < prev["end"]:
            return None, f"时间段 {fmt_dt(prev['start'])} 与 {fmt_dt(nxt['start'])} 重叠，请调整"
    return slots, None


def resolve_personnel(names: list[str]) -> tuple[list[Personnel] | None, str | None]:
    found = []
    for name in names:
        matches = list(Personnel.objects.filter(name=name).order_by("id")[:5])
        if len(matches) > 1:
            active = [p for p in matches if p.status == "active"]
            matches = active if len(active) == 1 else matches
        if not matches:
            return None, f"没有找到名为「{name}」的人员"
        if len(matches) > 1:
            listing = "；".join(f"{p.name}（{p.department or '未填部门'}，编号 {p.pk}）" for p in matches)
            return None, f"有多名叫「{name}」的人员：{listing}。请在页面上手动选择责任人"
        found.append(matches[0])
    return found, None


def resolve_equipments(names: list[str]) -> tuple[list[Equipment] | None, str | None]:
    found = []
    for name in names:
        matches = list(Equipment.objects.filter(name=name)[:2]) or list(
            Equipment.objects.filter(name__icontains=name).order_by("name")[:6]
        )
        if not matches:
            return None, f"没有找到名为「{name}」的设备"
        if len(matches) > 1:
            listing = "、".join(e.name for e in matches[:5])
            return None, f"「{name}」匹配到多台设备：{listing}。请说出完整名称"
        found.append(matches[0])
    return found, None


def find_conflicts(slots: list[dict], person_ids: list[int], equipment_ids: list[int], exclude_trial=None):
    """同一时段共用设备或责任人的其他进行中 / 计划中试验（最多 MAX_CONFLICTS 条提示）。"""
    if not person_ids and not equipment_ids:
        return []
    overlap = Q()
    for slot in slots:
        overlap |= Q(start_time__lt=slot["end"], end_time__gt=slot["start"])
    shared = Q()
    if person_ids:
        shared |= Q(trial__responsible_persons__in=person_ids)
    if equipment_ids:
        shared |= Q(trial__equipments__in=equipment_ids)
    qs = TimeSlot.objects.filter(overlap).filter(shared).exclude(trial__status__in=INACTIVE_STATUSES)
    if exclude_trial is not None:
        qs = qs.exclude(trial_id=exclude_trial)
    rows = qs.select_related("trial").order_by("start_time").distinct()
    warnings, seen = [], set()
    for slot in rows:
        if slot.trial_id in seen:
            continue
        seen.add(slot.trial_id)
        trial = slot.trial
        shared_names = [p.name for p in trial.responsible_persons.all() if p.pk in person_ids]
        shared_names += [e.name for e in trial.equipments.all() if e.pk in equipment_ids]
        warnings.append(
            f"时段冲突：「{trial.title}」{fmt_dt(slot.start_time)}–{fmt_dt(slot.end_time)}"
            f" 也使用 {'、'.join(shared_names) or '相同资源'}"
        )
        if len(warnings) >= MAX_CONFLICTS:
            break
    return warnings


def slot_label(slot: dict) -> str:
    text = f"{fmt_dt(slot['start'])} – {fmt_dt(slot['end'])}"
    return f"{text}（{slot['description']}）" if slot.get("description") else text


def trial_snapshot(trial: Trial) -> dict:
    return {
        "title": trial.title,
        "client": trial.client,
        "description": trial.description,
        "status": trial.status,
        "version": trial.version,
        "time_slots": [
            [_utc_iso(slot.start_time), _utc_iso(slot.end_time), slot.description]
            for slot in trial.time_slots.order_by("start_time", "id")
        ],
        "responsible_person_ids": sorted(trial.responsible_persons.values_list("id", flat=True)),
        "equipment_ids": sorted(trial.equipments.values_list("id", flat=True)),
    }


class TrialCreateTool(ConfirmedWriteTool):
    name = "trial_create"
    intent_type = "trial_create"
    description = "创建试验日程（含时间段、责任人、设备；写操作，需要确认，可撤销；仅管理员 / HR）"
    TASK_LABEL = "创建试验日程"
    FIELDS = {
        "title": "试验名称",
        "client": "客户单位（可为 null）",
        "description": "试验描述（可为 null）",
        "start_time": "开始时间 YYYY-MM-DDTHH:MM（只有一段时间时使用）",
        "end_time": "结束时间 YYYY-MM-DDTHH:MM（只有一段时间时使用）",
        "time_slots": '多段时间时使用：[{"start_time": ..., "end_time": ..., "description": ...}]，否则为 null',
        "responsible_persons": "责任人姓名列表（可为空列表）",
        "equipments": "设备名称列表（可为空列表）",
    }

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        slot = {
            "type": "object",
            "properties": {
                "start_time": {"type": "string", "description": "开始时间 YYYY-MM-DDTHH:MM"},
                "end_time": {"type": "string", "description": "结束时间 YYYY-MM-DDTHH:MM"},
                "description": {"type": "string", "description": "该时间段说明"},
            },
            "required": ["start_time", "end_time"],
            "additionalProperties": False,
        }
        return cls.build_schema(
            "创建试验日程（写操作，需要用户确认；仅管理员或 HR 可用，可撤销）。会提示设备或责任人的时段冲突。"
            "示例：'下周二 9 点到 17 点给某某研究所安排振动试验，责任人张三，用振动台'。",
            {
                "title": {"type": "string", "description": "试验名称"},
                "client": {"type": "string", "description": "客户单位"},
                "description": {"type": "string", "description": "试验描述"},
                "time_slots": {"type": "array", "items": slot, "description": "时间段（至少一段）"},
                "responsible_persons": {"type": "array", "items": {"type": "string"}, "description": "责任人姓名"},
                "equipments": {"type": "array", "items": {"type": "string"}, "description": "设备名称"},
            },
        )

    def dry_run(self, user, params, ctx):
        source = privileged_source(user)
        if source is None:
            return self.fail("只有管理员或 HR 可以创建试验日程")
        title = params.get("title").strip() if isinstance(params.get("title"), str) else ""
        if not title:
            return self.fail("请提供试验名称")
        if len(title) > 200:
            return self.fail("试验名称不能超过 200 字")
        client = params.get("client").strip()[:200] if isinstance(params.get("client"), str) else ""
        description = params.get("description").strip() if isinstance(params.get("description"), str) else ""
        slots, error = parse_slots(params)
        if error:
            return self.fail(error)
        person_names = _names(params.get("responsible_persons"))
        equipment_names = _names(params.get("equipments"))
        if len(person_names) > MAX_NAMES or len(equipment_names) > MAX_NAMES:
            return self.fail(f"责任人和设备各最多 {MAX_NAMES} 个")
        persons, error = resolve_personnel(person_names)
        if error:
            return self.fail(error)
        equipments, error = resolve_equipments(equipment_names)
        if error:
            return self.fail(error)
        person_ids = [p.pk for p in persons]
        equipment_ids = [e.pk for e in equipments]
        warnings = find_conflicts(slots, person_ids, equipment_ids)
        preview = build_preview(
            action="创建试验日程",
            target_type="试验",
            target_label=title,
            changes=[
                change("client", "客户单位", None, client or "—"),
                change("time_slots", "时间段", None, f"{len(slots)} 段，{fmt_dt(slots[0]['start'])} 起"),
                change("responsible_persons", "责任人", None, "、".join(p.name for p in persons) or "—"),
                change("equipments", "设备", None, "、".join(e.name for e in equipments) or "—"),
            ],
            affected_label="个试验",
            permission_source=source,
            items=[slot_label(slot) for slot in slots],
            warnings=warnings,
        )
        return self.draft(
            preview,
            {
                "title": title,
                "client": client,
                "description": description,
                "time_slots": [
                    {
                        "start_time": s["start"].isoformat(),
                        "end_time": s["end"].isoformat(),
                        "description": s["description"],
                    }
                    for s in slots
                ],
                "responsible_person_ids": person_ids,
                "equipment_ids": equipment_ids,
            },
        )

    def confirm(self, user, fields, ctx):
        title = fields.get("title") if isinstance(fields.get("title"), str) else ""
        slots, error = parse_slots({"time_slots": fields.get("time_slots")})
        if not title or error:
            return self.fail("确认内容缺失，请重新发起", code="stale_confirmation")
        if privileged_source(user) is None:
            return self.fail("你已没有创建试验日程的权限", code="permission_denied")
        person_ids = [int(i) for i in fields.get("responsible_person_ids") or []]
        equipment_ids = [int(i) for i in fields.get("equipment_ids") or []]
        with transaction.atomic():
            persons = list(Personnel.objects.filter(pk__in=person_ids))
            equipments = list(Equipment.objects.filter(pk__in=equipment_ids))
            if len(persons) != len(set(person_ids)) or len(equipments) != len(set(equipment_ids)):
                return self.fail("部分责任人或设备已被删除，请重新发起", code="stale_confirmation")
            trial = Trial.objects.create(
                title=title, client=fields.get("client") or "", description=fields.get("description") or ""
            )
            trial.responsible_persons.set(persons)
            trial.equipments.set(equipments)
            TimeSlot.objects.bulk_create(
                [
                    TimeSlot(trial=trial, start_time=s["start"], end_time=s["end"], description=s["description"])
                    for s in slots
                ]
            )
            trial.update_time_range()
            log = record_write(
                ctx,
                user,
                tool_name=self.intent_type,
                target_model=TARGET_MODEL,
                target_pk=trial.pk,
                operation="create",
                before=None,
                after=trial_snapshot(trial),
            )
        conflicts = find_conflicts(slots, person_ids, equipment_ids, exclude_trial=trial.pk)
        note = f"注意：与 {len(conflicts)} 个试验存在时段冲突。" if conflicts else ""
        return self.done(
            f"已创建试验日程「{title}」，共 {len(slots)} 个时间段，{fmt_dt(slots[0]['start'])} 开始。{note}",
            log,
            trial_id=trial.pk,
        )


class TrialCreateRevertHandler:
    """撤销创建：试验仍未被修改（快照一致）且仍有权限时删除。"""

    def revert(self, log, user):
        from ..writes.revert import RevertConflict, RevertResult

        if log.operation != "create":
            raise RevertConflict("该操作类型不支持回滚。")
        if privileged_source(user) is None:
            raise RevertConflict("你已没有管理试验日程的权限，无法撤销。")
        trial = Trial.objects.select_for_update().filter(pk=log.target_pk).first()
        if trial is None:
            raise RevertConflict("试验已不存在，无需撤销。")
        current = trial_snapshot(trial)
        if current != (log.after or {}):
            raise RevertConflict("试验已被修改，无法安全撤销；请在试验日程页处理。")
        trial.delete()
        return RevertResult(operation="delete", before=current, after=None, target_pk=str(log.target_pk))
