"""公告草稿（S3-2 写工具）。

AI 只能起草：确认后创建 ``status=draft`` 的公告，不通知任何人；由管理员 / HR 在
公告管理页点「发布」。权限与公告接口一致（管理员 / HR）。撤销 = 删除仍未发布、
未被修改的草稿。
"""

from __future__ import annotations

from django.db import transaction

from events.models import Announcement
from ..writes.preview import build_preview, change
from ..writes.write_log import record_write
from .write_base import ConfirmedWriteTool, privileged_source

TARGET_MODEL = "events.Announcement"
TITLE_MAX = 200
CONTENT_MAX = 20000
DRAFT_NOTICE = "保存为草稿，不会通知任何人；需由管理员或 HR 在「公告管理」页发布"


def announcement_snapshot(announcement: Announcement) -> dict:
    return {
        "title": announcement.title,
        "content": announcement.content,
        "status": announcement.status,
        "author_id": announcement.author_id,
    }


class AnnouncementDraftCreateTool(ConfirmedWriteTool):
    name = "announcement_draft_create"
    intent_type = "announcement_draft_create"
    description = "起草公司公告（只保存为草稿，由管理员 / HR 在公告管理页发布；写操作，需要确认，可撤销）"
    TASK_LABEL = "起草公告"
    FIELDS = {
        "title": "公告标题（不超过 200 字）",
        "content": "公告正文。用户只给了主题或要点时，请据此写出完整、正式的公告正文",
    }

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return cls.build_schema(
            "起草一条公司公告，保存为草稿（写操作，需要用户确认；仅管理员或 HR 可用；不会发布、不会通知任何人，"
            "发布需在公告管理页由人完成）。用户只给了主题时，请写出完整正文。示例：'起草一个国庆放假安排的公告'。",
            {
                "title": {"type": "string", "description": "公告标题（不超过 200 字）"},
                "content": {"type": "string", "description": "完整公告正文"},
            },
        )

    @staticmethod
    def _clean(params: dict) -> tuple[str, str]:
        title = params.get("title") if isinstance(params.get("title"), str) else ""
        content = params.get("content") if isinstance(params.get("content"), str) else ""
        return title.strip(), content.strip()

    def dry_run(self, user, params, ctx):
        source = privileged_source(user)
        if source is None:
            return self.fail("只有管理员或 HR 可以起草公告")
        title, content = self._clean(params)
        if not title:
            return self.fail("请提供公告标题")
        if len(title) > TITLE_MAX:
            return self.fail(f"公告标题不能超过 {TITLE_MAX} 字")
        if not content:
            return self.fail("请提供公告正文或要点")
        if len(content) > CONTENT_MAX:
            return self.fail(f"公告正文不能超过 {CONTENT_MAX} 字")
        preview = build_preview(
            action="起草公告",
            target_type="公告草稿",
            target_label=title,
            changes=[change("title", "标题", None, title), change("content", "正文", None, content)],
            affected_label="条公告草稿",
            permission_source=source,
            warnings=[DRAFT_NOTICE],
        )
        return self.draft(preview, {"title": title, "content": content})

    def confirm(self, user, fields, ctx):
        title, content = self._clean(fields)
        if not title or not content or len(title) > TITLE_MAX or len(content) > CONTENT_MAX:
            return self.fail("确认内容缺失，请重新发起", code="stale_confirmation")
        if privileged_source(user) is None:
            return self.fail("你已没有起草公告的权限", code="permission_denied")
        with transaction.atomic():
            announcement = Announcement.objects.create(
                title=title, content=content, author=user, status=Announcement.STATUS_DRAFT
            )
            log = record_write(
                ctx,
                user,
                tool_name=self.intent_type,
                target_model=TARGET_MODEL,
                target_pk=announcement.pk,
                operation="create",
                before=None,
                after=announcement_snapshot(announcement),
            )
        return self.done(
            f"已保存公告草稿「{title}」。草稿不会通知任何人，请到「公告管理」页检查后发布。",
            log,
            announcement_id=announcement.pk,
        )


class AnnouncementDraftRevertHandler:
    """撤销起草：草稿仍未发布、标题正文未被修改、且仍有权限时删除。"""

    def revert(self, log, user):
        from ..writes.revert import RevertConflict, RevertResult

        if log.operation != "create":
            raise RevertConflict("该操作类型不支持回滚。")
        if privileged_source(user) is None:
            raise RevertConflict("你已没有管理公告的权限，无法撤销。")
        announcement = Announcement.objects.select_for_update().filter(pk=log.target_pk).first()
        if announcement is None:
            raise RevertConflict("公告草稿已不存在，无需撤销。")
        if announcement.status != Announcement.STATUS_DRAFT:
            raise RevertConflict(
                "公告已发布，无法撤销；如需撤回请在「公告管理」页处理。", current={"status": "published"}
            )
        current = announcement_snapshot(announcement)
        expected = log.after or {}
        if current["title"] != expected.get("title") or current["content"] != expected.get("content"):
            raise RevertConflict("公告草稿已被修改，无法安全撤销；请在「公告管理」页处理。")
        announcement.delete()
        return RevertResult(operation="delete", before=current, after=None, target_pk=str(log.target_pk))
