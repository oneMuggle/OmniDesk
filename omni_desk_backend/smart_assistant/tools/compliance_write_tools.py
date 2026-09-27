"""合规问题状态更新（S3-1 写工具）。

权限与页面接口一致：管理员或项目负责人（``ComplianceChecker.can_modify_issue``）；
确认卡片显示权限来源。确认时按 ``updated_at`` 做版本校验；撤销时再次校验权限。
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q

from compliance.models import ComplianceIssue
from compliance.services.compliance_engine import ComplianceChecker

from ..writes.preview import build_preview, change
from ..writes.write_log import record_write
from .write_base import STALE_MESSAGE, ConfirmedWriteTool

TARGET_MODEL = "compliance.ComplianceIssue"
VALID_STATUSES = [value for value, _ in ComplianceIssue.STATUS_CHOICES]


def permission_source(user, issue) -> str:
    if issue.project.manager_id == user.pk:
        return "项目负责人"
    if user.is_staff:
        return "管理员（非本人负责的项目）"
    return "—"


def issue_label(issue) -> str:
    desc = (issue.description or "").strip().replace("\n", " ")
    return f"#{issue.pk} {issue.project.name} · {desc[:30]}"


class ComplianceStatusUpdateTool(ConfirmedWriteTool):
    name = "compliance_issue_update_status"
    intent_type = "compliance_issue_update_status"
    description = "更新合规问题的处理状态（待处理 / 处理中 / 已解决 / 已忽略；写操作，需要确认，可撤销）"
    TASK_LABEL = "更新合规问题状态"
    FIELDS = {
        "issue_id": "合规问题 ID（整数；用户没提时为 null）",
        "keyword": "问题描述或位置中的关键词（可为 null）",
        "project": "项目名称关键词（可为 null）",
        "new_status": "目标状态，只能是：" + " / ".join(VALID_STATUSES),
    }

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return cls.build_schema(
            "更新合规问题的处理状态（写操作，需要用户确认；仅管理员或项目负责人可用，可撤销）。"
            "示例：'把 A 项目封面缺页码那条合规问题标为已解决'。",
            {
                "issue_id": {"type": "integer", "description": "合规问题 ID"},
                "keyword": {"type": "string", "description": "问题描述或位置关键词"},
                "project": {"type": "string", "description": "项目名称关键词"},
                "new_status": {"type": "string", "enum": VALID_STATUSES, "description": "目标状态"},
            },
        )

    def dry_run(self, user, params, ctx):
        new_status = params.get("new_status")
        if new_status not in VALID_STATUSES:
            return self.fail("请说明要改成哪个状态：" + " / ".join(VALID_STATUSES))
        qs = ComplianceChecker.get_visible_issues(user)
        issue_id = params.get("issue_id")
        keyword = params.get("keyword").strip() if isinstance(params.get("keyword"), str) else ""
        project = params.get("project").strip() if isinstance(params.get("project"), str) else ""
        if issue_id in (None, "") and not keyword and not project:
            return self.fail("请说明是哪一条合规问题（编号、项目或问题描述）")
        if issue_id not in (None, ""):
            try:
                qs = qs.filter(pk=int(issue_id))
            except (TypeError, ValueError):
                return self.fail("合规问题编号应为数字")
        if keyword:
            qs = qs.filter(Q(description__icontains=keyword) | Q(location__icontains=keyword))
        if project:
            qs = qs.filter(project__name__icontains=project)
        rows = list(qs.order_by("-created_at")[:6])
        if not rows:
            return self.fail("没有找到你可见的匹配合规问题")
        if len(rows) > 1:
            listing = "；".join(f"{issue_label(i)}（{i.status}）" for i in rows[:5])
            return self.fail(f"找到多条匹配的合规问题：{listing}。请指明是哪一条")
        issue = rows[0]
        if not ComplianceChecker.can_modify_issue(user, issue):
            return self.fail("你没有权限修改该项目下的合规问题")
        if issue.status == new_status:
            return self.fail(f"该问题当前已是「{new_status}」")
        preview = build_preview(
            action="更新合规问题状态",
            target_type="合规问题",
            target_label=issue_label(issue),
            changes=[change("status", "状态", issue.status, new_status)],
            affected_label="条合规问题",
            permission_source=permission_source(user, issue),
        )
        return self.draft(
            preview,
            {
                "issue_id": issue.pk,
                "old_status": issue.status,
                "new_status": new_status,
                "version": issue.updated_at.isoformat(),
            },
        )

    def confirm(self, user, fields, ctx):
        new_status = fields.get("new_status")
        if new_status not in VALID_STATUSES:
            return self.fail("确认内容缺失，请重新发起", code="stale_confirmation")
        with transaction.atomic():
            issue = ComplianceIssue.objects.select_for_update().filter(pk=fields.get("issue_id")).first()
            if issue is None:
                return self.fail("合规问题已不存在", code="stale_confirmation")
            if fields.get("version") and issue.updated_at.isoformat() != fields["version"]:
                return self.fail(STALE_MESSAGE, code="stale_confirmation")
            if not ComplianceChecker.can_modify_issue(user, issue):
                return self.fail("你已没有权限修改该合规问题", code="permission_denied")
            old_status = issue.status
            issue.status = new_status
            issue.save(update_fields=["status", "updated_at"])
            log = record_write(
                ctx,
                user,
                tool_name=self.intent_type,
                target_model=TARGET_MODEL,
                target_pk=issue.pk,
                operation="update",
                before={"status": old_status},
                after={"status": new_status},
            )
        return self.done(
            f"已将合规问题 {issue_label(issue)} 的状态从「{old_status}」改为「{new_status}」", log, issue_id=issue.pk
        )


class ComplianceStatusRevertHandler:
    """撤销状态更新：当前状态仍等于本次设置的值、且仍有权限时恢复原状态。"""

    def revert(self, log, user):
        from ..writes.revert import RevertConflict, RevertResult

        if log.operation != "update":
            raise RevertConflict("该操作类型不支持回滚。")
        issue = ComplianceIssue.objects.select_for_update().filter(pk=log.target_pk).first()
        if issue is None:
            raise RevertConflict("合规问题已不存在，无法撤销。")
        if not ComplianceChecker.can_modify_issue(user, issue):
            raise RevertConflict("你已没有权限修改该合规问题，无法撤销。")
        expected = (log.after or {}).get("status")
        if issue.status != expected:
            raise RevertConflict("合规问题状态已被修改，无法安全撤销。", current={"status": issue.status})
        restored = (log.before or {}).get("status")
        if restored not in VALID_STATUSES:
            raise RevertConflict("原状态无效，无法撤销。")
        issue.status = restored
        issue.save(update_fields=["status", "updated_at"])
        return RevertResult(
            operation="update", before={"status": expected}, after={"status": restored}, target_pk=str(issue.pk)
        )
