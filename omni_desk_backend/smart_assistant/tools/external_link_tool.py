"""ExternalLinkTool - 内网外链导航(ExternalLink)查询工具.

对应交接文档任务 3.1:
- 数据源:external_integration.ExternalLink
- 过滤:仅 active
- 关键词匹配:name / description / category
- 上限 20 条,按 category / sort_order / name 排序(模型 Meta 自带)
- SSO 信息按 sso_enabled 条件返回
"""

from typing import TYPE_CHECKING

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
    risk_level = "read"  # 显式声明:只读查询工具,无副作用
    required_auth = True

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        # 字符级别 strip,故停用词也用单字。
        # 业务核心词("登"/"录" 等 VPN/SSO 高频词)**不**放 stopwords —— 否则
        # 用户说 "VPN 怎么登录" 会被退化为 list_all 模式(返回所有 active 链接),
        # 而非精确匹配 name="公司VPN"。这与 compliance_tool 同类设计权衡一致。
        stopwords = {"怎", "么", "如", "何", "使", "用", "打", "开", "访", "问", "的", "什"}

        # 支持两种调用方式(向后兼容):
        # - 旧:execute(query, context) — 原生 tool_calls 旧签名/直调路径
        # - 新:execute(params, scope, qs) — scope-aware 执行分支(C-1 修复)
        if qs is not None and scope is not None:
            search_query = params.get("query") if isinstance(params, dict) and params.get("query") else (query or "")
            keywords = "".join(c for c in search_query if c not in stopwords).strip()
            links_qs = qs.filter(is_active=True)
        else:
            search_query = query or ""
            keywords = "".join(c for c in search_query if c not in stopwords).strip()
            links_qs = ExternalLink.objects.filter(is_active=True)

        # 用户说"所有"/"全部"或没有关键词时,返回所有 active
        list_all = "所有" in search_query or "全部" in search_query or not keywords

        if not list_all and keywords and len(keywords) >= 2:
            links_qs = links_qs.filter(
                Q(name__icontains=keywords) | Q(description__icontains=keywords) | Q(category__icontains=keywords)
            )

        links: list[dict] = []
        for link in links_qs[:20]:
            links.append(
                {
                    "name": link.name,
                    "url": link.url,
                    "category": link.category,
                    "description": (link.description or "")[:150],
                    "sso_enabled": link.sso_enabled,
                    "sso_token_endpoint": link.sso_token_endpoint if link.sso_enabled else None,
                }
            )

        if not links:
            return {
                "found": False,
                "count": 0,
                "links": [],
                "message": f'未找到与 "{keywords or query}" 相关的外链',
            }

        return {"found": True, "count": len(links), "links": links}

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 查询公司内网外链导航。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询公司内网外链导航(VPN/Jira 等),仅返回 active 链接。"
                    "示例 query: 'VPN 怎么登录'、'所有 Jira 入口'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词,匹配 name/description/category;空则返回所有 active",
                        },
                        "category": {
                            "type": "string",
                            "description": "按 category 过滤(可选)",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def build_base_queryset(self):
        """返回未过滤的外链 QuerySet(execute 中会再加 is_active filter)。"""
        return ExternalLink.objects.all()

    def _scope_self(self, qs, ctx):
        """本人范围:外链是公共导航数据,无"本人"语义;返回空 QuerySet。"""
        return qs.none()
