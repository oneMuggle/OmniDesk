"""通知标记已读（S3-1 写工具）。

只能处理本人的通知；可指定 ID、按标题关键词或全部未读，单次最多 50 条。
撤销时只恢复本次标记、且之后没有再被处理过的那些通知。
"""

from __future__ import annotations

from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils import timezone

from notifications.models import Notification

from ..writes.preview import build_preview, change
from ..writes.write_log import record_write
from .write_base import ConfirmedWriteTool

MAX_BATCH = 50
TARGET_MODEL = "notifications.Notification"


def _utc_iso(value) -> str | None:
    return value.astimezone(dt_timezone.utc).isoformat() if value else None


def _as_ids(value) -> list[int]:
    if not isinstance(value, list):
        return []
    ids = []
    for item in value:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return ids[:MAX_BATCH]


class NotificationMarkReadTool(ConfirmedWriteTool):
    name = "notification_mark_read"
    intent_type = "notification_mark_read"
    description = "把我的站内通知标记为已读（可指定通知、按标题关键词或全部未读；写操作，需要确认）"
    TASK_LABEL = "标记通知为已读"
    FIELDS = {
        "notification_ids": "要标记的通知 ID 列表（整数数组；用户没提 ID 时为 null）",
        "keyword": "通知标题中的关键词（可为 null）",
        "all_unread": "是否把全部未读通知都标为已读（true / false）",
    }

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return cls.build_schema(
            "把当前用户的站内通知标记为已读（写操作，需要用户确认；单次最多 50 条，可撤销）。"
            "示例：'把未读通知都标为已读'、'把会议相关的通知标为已读'。",
            {
                "notification_ids": {"type": "array", "items": {"type": "integer"}, "description": "通知 ID"},
                "keyword": {"type": "string", "description": "通知标题关键词"},
                "all_unread": {"type": "boolean", "description": "是否处理全部未读通知"},
            },
        )

    def dry_run(self, user, params, ctx):
        qs = Notification.objects.filter(user=user, is_read=False)
        ids = _as_ids(params.get("notification_ids"))
        keyword = (params.get("keyword") or "").strip() if isinstance(params.get("keyword"), str) else ""
        if ids:
            qs = qs.filter(id__in=ids)
        elif keyword:
            qs = qs.filter(title__icontains=keyword)
        elif params.get("all_unread") not in (True, "true", "True"):
            return self.fail("请说明要标记哪些通知：指定通知、标题关键词，或「全部未读」")
        total = qs.count()
        if total == 0:
            return self.fail("没有符合条件的未读通知")
        if total > MAX_BATCH:
            return self.fail(f"符合条件的未读通知有 {total} 条，单次最多处理 {MAX_BATCH} 条，请缩小范围")
        rows = list(qs.order_by("-created_at").only("id", "title"))
        label = rows[0].title if total == 1 else f"{total} 条未读通知"
        preview = build_preview(
            action="标记通知为已读",
            target_type="通知",
            target_label=label,
            changes=[change("is_read", "状态", "未读", "已读")],
            affected_count=total,
            affected_label="条通知",
            permission_source="本人的通知",
            items=[row.title for row in rows],
        )
        return self.draft(preview, {"notification_ids": [row.id for row in rows]})

    def confirm(self, user, fields, ctx):
        ids = _as_ids(fields.get("notification_ids"))
        if not ids:
            return self.fail("确认内容缺失，请重新发起", code="stale_confirmation")
        with transaction.atomic():
            rows = list(
                Notification.objects.select_for_update().filter(user=user, id__in=ids, is_read=False).order_by("id")
            )
            if not rows:
                return self.fail("这些通知已经是已读状态，无需再次标记", code="state_conflict")
            now = timezone.now()
            row_ids = [row.id for row in rows]
            Notification.objects.filter(id__in=row_ids).update(is_read=True, read_at=now)
            log = record_write(
                ctx,
                user,
                tool_name=self.intent_type,
                target_model=TARGET_MODEL,
                target_pk=row_ids[0] if len(row_ids) == 1 else f"batch:{len(row_ids)}",
                operation="update",
                before={"items": {str(i): {"is_read": False, "read_at": None} for i in row_ids}},
                after={"items": {str(i): {"is_read": True, "read_at": _utc_iso(now)} for i in row_ids}},
            )
        skipped = len(ids) - len(row_ids)
        summary = f"已将 {len(row_ids)} 条通知标为已读"
        if skipped:
            summary += f"（{skipped} 条此前已读，已跳过）"
        return self.done(summary, log, count=len(row_ids))


class NotificationReadRevertHandler:
    """撤销「标为已读」：只恢复仍保持本次写入状态的通知。"""

    def revert(self, log, user):
        from ..writes.revert import RevertConflict, RevertResult

        if log.operation != "update":
            raise RevertConflict("该操作类型不支持回滚。")
        items = (log.after or {}).get("items") or {}
        ids = [int(i) for i in items]
        rows = list(Notification.objects.select_for_update().filter(user=user, id__in=ids))
        restorable = [row for row in rows if row.is_read and _utc_iso(row.read_at) == items[str(row.id)].get("read_at")]
        if not restorable:
            raise RevertConflict("这些通知的状态已变化，无法撤销。")
        restore_ids = [row.id for row in restorable]
        Notification.objects.filter(id__in=restore_ids).update(is_read=False, read_at=None)
        return RevertResult(
            operation="update",
            before={"items": {str(i): items[str(i)] for i in restore_ids}},
            after={"items": {str(i): {"is_read": False, "read_at": None} for i in restore_ids}},
            target_pk=log.target_pk,
        )
