"""ComplianceTool - 合规问题/待整改项(ComplianceIssue)查询工具.

对应交接文档任务 2.1:
- 数据源:compliance.ComplianceIssue
- 过滤:未完成(status IN 待处理/处理中)
- 关键词匹配:description / issue_type / project.name
- 紧急程度过滤:severity="紧急"
- 即将到期过滤:due_date <= today+7
- 上限 10 条,按 severity 倒序、due_date 升序
- N+1 防护:select_related("project", "document_book", "document_template")
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING, List

from django.db.models import Q

from compliance.models import ComplianceIssue

from .base import BaseTool

if TYPE_CHECKING:
    from .tool_context import ToolContext


class ComplianceTool(BaseTool):
    """查询合规问题/待整改项(compliance.ComplianceIssue)."""

    name = "compliance_query"
    description = "查询合规问题/待整改项(compliance.ComplianceIssue)"
    intent_type = "compliance_query"
    required_auth = True

    def execute(self, query: str, context: "ToolContext") -> dict:
        # 单字停用词集合(注意:字符级别 strip 必须用单字,见下)
        stopwords = {"合", "规", "整", "改", "待", "已", "什", "么", "查", "看", "几", "条"}
        keywords = "".join(c for c in query if c not in stopwords).strip()

        qs = (
            ComplianceIssue.objects
            .filter(status__in=["待处理", "处理中"])
            .select_related("project", "document_book", "document_template")
            .order_by("-severity", "due_date")
        )

        # 关键词过滤(至少 2 字符,避免单字过宽)
        if keywords and len(keywords) >= 2:
            qs = qs.filter(
                Q(description__icontains=keywords) |
                Q(issue_type__icontains=keywords) |
                Q(project__name__icontains=keywords)
            )

        # 即将到期(7 天内)关键词
        if "即将" in query or "快到期" in query:
            qs = qs.filter(due_date__lte=date.today() + timedelta(days=7))

        # 紧急
        if "紧急" in query:
            qs = qs.filter(severity="紧急")

        issues: List[dict] = []
        for i in qs[:10]:
            issues.append({
                "issue_type": i.issue_type,
                "description": i.description[:200],
                "status": i.status,
                "severity": i.severity,
                "project": i.project.name if i.project else "无",
                "due_date": i.due_date.isoformat() if i.due_date else None,
                "location": i.location,
            })

        if not issues:
            return {"found": False, "message": f'未找到与 "{keywords or query}" 相关的合规问题'}

        return {"found": True, "count": len(issues), "issues": issues}
