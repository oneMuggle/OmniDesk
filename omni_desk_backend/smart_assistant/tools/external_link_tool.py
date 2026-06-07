"""ExternalLinkTool - 内网外链导航(ExternalLink)查询工具.

对应交接文档任务 3.1:
- 数据源:external_integration.ExternalLink
- 过滤:仅 active
- 关键词匹配:name / description / category
- 上限 20 条,按 category / sort_order / name 排序(模型 Meta 自带)
- SSO 信息按 sso_enabled 条件返回
"""

from typing import TYPE_CHECKING, List

from django.db.models import Q

from external_integration.models import ExternalLink

from .base import BaseTool

if TYPE_CHECKING:
    from .tool_context import ToolContext


class ExternalLinkTool(BaseTool):
    """查询公司内网外链导航(VPN/Jira 等,external_integration.ExternalLink)."""

    name = "external_link_query"
    description = "查询公司内网外链(VPN/Jira 等,external_integration.ExternalLink)"
    intent_type = "external_link_query"
    required_auth = True

    def execute(self, query: str, context: "ToolContext") -> dict:
        # 字符级别 strip,故停用词也用单字
        stopwords = {"怎", "么", "如", "何", "登", "录", "使", "用", "打", "开", "访", "问", "的", "什"}
        keywords = "".join(c for c in query if c not in stopwords).strip()

        qs = ExternalLink.objects.filter(is_active=True)

        # 用户说"所有"/"全部"或没有关键词时,返回所有 active
        list_all = "所有" in query or "全部" in query or not keywords

        if not list_all and keywords and len(keywords) >= 2:
            qs = qs.filter(
                Q(name__icontains=keywords) |
                Q(description__icontains=keywords) |
                Q(category__icontains=keywords)
            )

        links: List[dict] = []
        for l in qs[:20]:
            links.append({
                "name": l.name,
                "url": l.url,
                "category": l.category,
                "description": (l.description or "")[:150],
                "sso_enabled": l.sso_enabled,
                "sso_token_endpoint": l.sso_token_endpoint if l.sso_enabled else None,
            })

        if not links:
            return {
                "found": False,
                "count": 0,
                "links": [],
                "message": f'未找到与 "{keywords or query}" 相关的外链',
            }

        return {"found": True, "count": len(links), "links": links}
