"""合规专员：跟踪即将到期 / 已逾期的合规问题，起草整改建议（S4-1）。

- 每位项目负责人每天一条汇总提醒（与 ``check_compliance_due_dates`` 的单条逾期升级提醒互补）。
- 逾期或紧急的问题：LLM 起草整改建议（配额用完或失败时按问题类型用模板清单降级），
  生成「保存整改建议」待确认事项；负责人确认后存为本人备忘录，可撤销。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from ...writes.preview import build_preview, change
from ..runtime import RoleRunner

DUE_WITHIN_DAYS = 3
ACTIVE_STATUSES = ("待处理", "处理中", "紧急")
MAX_SUGGESTION_CHARS = 600
#: 负责人取消后，多少天内不再为同一问题起草建议
REJECT_COOLDOWN = timedelta(days=7)

TEMPLATE_SUGGESTIONS = {
    "不规范": [
        "对照现行模板逐项核对格式、签字与日期",
        "补齐缺失的审核或批准记录",
        "整理后由第二人复核并留存复核记录",
    ],
    "时间冲突": [
        "核对相关记录的时间线，找出冲突的时间点",
        "与当事人确认实际发生时间并书面说明",
        "按规定方式更正记录，保留更正痕迹",
    ],
    "内容缺失": [
        "列出缺失的条目并确定责任人",
        "从原始记录或数据中补录缺失内容",
        "补录后由负责人签字确认",
    ],
    "内容与规定不符": [
        "对照适用的规定或方案找出不符项",
        "评估不符项对结果的影响并记录",
        "制定纠正措施并跟踪完成情况",
    ],
}
DEFAULT_TEMPLATE = ["明确问题范围与责任人", "制定整改措施和完成时间", "整改完成后复核并留存记录"]


def template_suggestion(issue) -> str:
    items = TEMPLATE_SUGGESTIONS.get(issue.issue_type, DEFAULT_TEMPLATE)
    return "\n".join(f"- {item}" for item in items)


def suggestion_dedupe_key(issue) -> str:
    return f"compliance_suggestion:{issue.pk}"


def issue_label(issue) -> str:
    return f"{issue.project.name} · {issue.issue_type}"


def reminder_for(due_date, today):
    """提醒时间取到期日 09:00；已过期则不设提醒。"""
    from ..runtime import day_start

    if due_date is None or due_date < today:
        return None
    return day_start(due_date) + timedelta(hours=9)


class ComplianceRunner(RoleRunner):
    def run(self):
        from compliance.models import ComplianceIssue

        today = self.ctx.today
        issues = (
            ComplianceIssue.objects.filter(
                status__in=ACTIVE_STATUSES,
                due_date__isnull=False,
                due_date__lte=today + timedelta(days=DUE_WITHIN_DAYS),
            )
            .select_related("project__manager")
            .order_by("due_date", "id")
        )
        by_manager = defaultdict(list)
        for issue in issues:
            self.ctx.stats["issues"] += 1
            manager = getattr(issue.project, "manager", None)
            if manager is None or not manager.is_active:
                self.ctx.stats["issues_without_manager"] += 1
                continue
            by_manager[manager].append(issue)
        for manager, items in by_manager.items():
            self.send_digest(manager, items)
            for issue in items:
                if issue.due_date < today or issue.status == "紧急" or issue.severity == "紧急":
                    self.suggest(manager, issue)

    def send_digest(self, manager, items):
        today = self.ctx.today
        lines = []
        for issue in items[:20]:
            days = (issue.due_date - today).days
            when = f"已逾期 {-days} 天" if days < 0 else ("今天到期" if days == 0 else f"{days} 天后到期")
            lines.append(f"- 【{when}】{issue_label(issue)}：{issue.description[:60]}")
        if len(items) > 20:
            lines.append(f"- ……另有 {len(items) - 20} 个")
        self.ctx.notify(
            manager,
            title=f"合规提醒：{len(items)} 个问题即将到期或已逾期",
            content="\n".join(lines),
            dedupe_key=f"agent_compliance:digest:{today.isoformat()}",
        )

    def _already_handled(self, manager, issue) -> bool:
        from smart_assistant.models import AgentProposal

        key = suggestion_dedupe_key(issue)
        if self.ctx.has_open_proposal(manager, key):
            return True
        history = AgentProposal.objects.filter(user=manager, dedupe_key=key)
        if history.filter(status=AgentProposal.STATUS_APPROVED).exists():
            return True
        return history.filter(
            status=AgentProposal.STATUS_REJECTED, decided_at__gte=timezone.now() - REJECT_COOLDOWN
        ).exists()

    def suggest(self, manager, issue):
        if self._already_handled(manager, issue):
            self.ctx.stats["skipped_duplicate"] += 1
            return
        prompt = (
            f"问题类型：{issue.issue_type}\n严重程度：{issue.severity}\n"
            f"位置：{(issue.location or '未注明')[:100]}\n问题描述：{issue.description[:500]}"
        )
        text = self.ctx.llm(self.ctx.profile.system_prompt, prompt, purpose="compliance_suggestion")
        source = "llm" if text else "template"
        suggestion = (text or template_suggestion(issue))[:MAX_SUGGESTION_CHARS]
        memo_title = f"整改：{issue_label(issue)}"[:200]
        reminder = reminder_for(issue.due_date, self.ctx.today)
        warnings = ["建议由 AI 生成，仅供参考，请结合实际核对。"] if source == "llm" else ["建议来自通用模板。"]
        preview = build_preview(
            action="保存整改建议",
            target_type="合规问题",
            target_label=issue_label(issue),
            changes=[
                change("title", "备忘录标题", None, memo_title),
                change(
                    "reminder_time",
                    "提醒时间",
                    None,
                    timezone.localtime(reminder).strftime("%Y-%m-%d %H:%M") if reminder else "不提醒（已逾期）",
                ),
            ],
            affected_label="条备忘录",
            permission_source="本人负责的项目",
            items=[line for line in suggestion.splitlines() if line.strip()][:5],
            warnings=warnings,
        )
        self.ctx.propose(
            manager,
            kind="compliance_suggestion",
            title=f"保存整改建议：{issue_label(issue)}",
            fields={"issue_id": issue.pk, "suggestion": suggestion, "source": source},
            preview=preview,
            dedupe_key=suggestion_dedupe_key(issue),
            content=f"合规问题「{issue_label(issue)}」{issue.description[:60]}，已起草整改建议，点击后确认是否存为备忘录。",
        )
