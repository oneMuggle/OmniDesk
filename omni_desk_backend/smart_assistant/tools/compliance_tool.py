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

from django.db.models import Case, IntegerField, Q, Value, When

from compliance.models import ComplianceIssue

from .base import BaseTool

# 按业务优先级定义 severity 排序:紧急 > 高 > 中 > 低
# 不用字符串倒序是因为 CharField 的字典序与业务优先级不一致
# (Unicode:高 U+9AD8 > 紧 U+7D27 > 低 U+4F4E > 中 U+4E2D)
_SEVERITY_RANK = Case(
    When(severity="紧急", then=Value(0)),
    When(severity="高", then=Value(1)),
    When(severity="中", then=Value(2)),
    When(severity="低", then=Value(3)),
    default=Value(4),
    output_field=IntegerField(),
)


class ComplianceTool(BaseTool):
    """查询合规问题/待整改项(compliance.ComplianceIssue)."""

    name = "compliance_query"
    description = "查询合规问题/待整改项(compliance.ComplianceIssue)"
    intent_type = "compliance_query"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用
    required_auth = True

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        # 字符级别 strip,故停用词也用单字。
        # 注意:不在 stopwords 中放"改"/"整"等业务核心动词 —— "整改"是合规领域
        # 的核心术语,必须保留作为关键词,否则用户说"整改"会被全 strip 掉。
        stopwords = {"合", "规", "待", "已", "什", "么", "查", "看", "几", "条"}

        # 支持两种调用方式(向后兼容):
        # - 旧:execute(query, context) — 原生 tool_calls 旧签名/直调路径
        # - 新:execute(params, scope, qs) — scope-aware 执行分支(C-1 修复)
        if qs is not None and scope is not None:
            search_query = params.get("query") if isinstance(params, dict) and params.get("query") else (query or "")
            keywords = "".join(c for c in search_query if c not in stopwords).strip()
            issues_qs = (
                qs.filter(status__in=["待处理", "处理中"])
                .select_related("project", "document_book", "document_template")
                .order_by(_SEVERITY_RANK, "due_date")
            )
        else:
            search_query = query or ""
            keywords = "".join(c for c in search_query if c not in stopwords).strip()
            issues_qs = (
                ComplianceIssue.objects.filter(status__in=["待处理", "处理中"])
                .select_related("project", "document_book", "document_template")
                .order_by(_SEVERITY_RANK, "due_date")
            )

        # 关键词过滤(至少 2 字符,避免单字过宽)
        if keywords and len(keywords) >= 2:
            issues_qs = issues_qs.filter(
                Q(description__icontains=keywords)
                | Q(issue_type__icontains=keywords)
                | Q(project__name__icontains=keywords)
            )

        # 即将到期(7 天内)关键词
        if "即将" in search_query or "快到期" in search_query:
            issues_qs = issues_qs.filter(due_date__lte=date.today() + timedelta(days=7))

        # 紧急
        if "紧急" in search_query:
            issues_qs = issues_qs.filter(severity="紧急")

        issues: list[dict] = []
        for i in issues_qs[:10]:
            raw_desc = i.description or ""
            truncated = raw_desc[:200] + ("..." if len(raw_desc) > 200 else "")
            issues.append(
                {
                    "issue_type": i.issue_type,
                    "description": truncated,
                    "status": i.status,
                    "severity": i.severity,
                    "project": i.project.name if i.project else "无",
                    "due_date": i.due_date.isoformat() if i.due_date else None,
                    "location": i.location,
                }
            )

        if not issues:
            return {"found": False, "message": f'未找到与 "{keywords or query}" 相关的合规问题'}

        return {"found": True, "count": len(issues), "issues": issues}

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 查询合规问题/待整改项。

        severity 用 JSON Schema enum 限制取值(紧急/高/中/低);
        keywords/due_within_days/severity 三个可选过滤维度。
        """
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询合规问题/待整改项(compliance.ComplianceIssue),"
                    "仅返回待处理/处理中状态。按 severity 倒序、due_date 升序。"
                    "示例 query: '紧急整改项'、'即将到期的合规问题'、'研发项目待整改'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词,匹配 description/issue_type/project.name",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["紧急", "高", "中", "低"],
                            "description": "按紧急程度精确过滤(可选)",
                        },
                        "due_within_days": {
                            "type": "integer",
                            "description": "仅返回 N 天内到期的项(可选)",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def build_base_queryset(self):
        """返回未过滤的合规问题 QuerySet(主数据源,execute 中已加 status filter)。"""
        return ComplianceIssue.objects.select_related("project", "document_book", "document_template").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 作为项目负责人管理的项目下的合规问题(经 project.manager 关系)。"""
        return qs.filter(project__manager=ctx.user)
