# omni_desk_backend/search_federation/providers.py
"""联邦搜索：内部业务模块 provider 注册与聚合。

设计要点
--------
- 每个 provider 绑定一个智能助手工具（``tool_intent``），数据范围通过
  ``tool.scoped_queryset(context)`` 获取，与 AI 查询共用 SELF / DEPARTMENT /
  GLOBAL 三级 scope，不另写一套权限。
- 失败时关闭（fail closed）：取不到工具、工具没有 scope 能力，或查询出错时，
  跳过该 provider，**绝不**回退到 ``Model.objects.all()``。
- 结果只保留检索展示所需的最少字段（source/id/title/subtitle/url），
  不返回手机号、住址等敏感信息。
- ``url`` 必须指向前端实际存在的路由。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import reduce
from operator import or_
from typing import Any

from django.db.models import Q

from observability import get_logger

logger = get_logger(__name__, "search_federation.providers")

DEFAULT_LIMIT = 5
MAX_LIMIT = 20
MAX_QUERY_LENGTH = 100


def _truncate(text: str | None, length: int = 60) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= length else text[:length] + "…"


@dataclass(frozen=True)
class SearchProvider:
    """一个内部检索来源。"""

    source: str
    label: str
    tool_intent: str
    search_fields: tuple[str, ...]
    to_result: Callable[[Any, Any], dict]
    order_by: tuple[str, ...] = ("-pk",)

    def search(self, context: Any, query: str, limit: int) -> list[dict]:
        from smart_assistant.tools.registry import ToolRegistry

        user = getattr(context, "user", None)
        tool = ToolRegistry.get_tool_for_user(self.tool_intent, user)
        if tool is None or not getattr(tool, "supports_scope_filter", False):
            return []
        qs = tool.scoped_queryset(context)
        if qs is None:
            return []
        condition = reduce(or_, (Q(**{f"{field}__icontains": query}) for field in self.search_fields))
        rows = qs.filter(condition).order_by(*self.order_by)[:limit]
        return [self.to_result(obj, context) for obj in rows]


# ---------------------------------------------------------------------------
# 各模块结果转换
# ---------------------------------------------------------------------------


def _project_result(obj, _ctx) -> dict:
    return {
        "source": "project",
        "id": obj.pk,
        "title": obj.name,
        "subtitle": _truncate(obj.description),
        "url": "/control-panel/projects",
    }


def _memo_result(obj, _ctx) -> dict:
    return {
        "source": "memo",
        "id": obj.pk,
        "title": obj.title,
        "subtitle": _truncate(obj.content),
        "url": "/memos",
    }


def _personnel_result(obj, ctx) -> dict:
    user = getattr(ctx, "user", None)
    # CustomUser.personnel 为 OneToOne（反向名 user_account），用正向外键 id 判断本人
    is_self = user is not None and getattr(user, "personnel_id", None) == obj.pk
    position = getattr(obj.position, "name", "") if obj.position_id else ""
    subtitle = " · ".join(part for part in (obj.department, position) if part)
    return {
        "source": "personnel",
        "id": obj.pk,
        "title": obj.name,
        "subtitle": subtitle,
        "url": "/me/personnel" if is_self else f"/control-panel/personnel/{obj.pk}",
    }


def _compliance_result(obj, _ctx) -> dict:
    issue_type = obj.get_issue_type_display() if hasattr(obj, "get_issue_type_display") else obj.issue_type
    project_name = obj.project.name if obj.project_id else ""
    return {
        "source": "compliance",
        "id": obj.pk,
        "title": f"{issue_type}：{_truncate(obj.description, 40)}",
        "subtitle": " · ".join(part for part in (project_name, obj.status) if part),
        "url": "/control-panel/compliance",
    }


def _document_result(obj, _ctx) -> dict:
    template_type = obj.get_template_type_display() if hasattr(obj, "get_template_type_display") else obj.template_type
    return {
        "source": "document",
        "id": obj.pk,
        "title": obj.name,
        "subtitle": template_type or "",
        "url": "/control-panel/documents",
    }


PROVIDERS: tuple[SearchProvider, ...] = (
    SearchProvider("project", "项目", "project_status", ("name", "description"), _project_result),
    SearchProvider("memo", "备忘录", "memo_query", ("title", "content"), _memo_result),
    SearchProvider("personnel", "人员", "personnel_query", ("name", "department"), _personnel_result),
    SearchProvider(
        "compliance",
        "合规问题",
        "compliance_query",
        ("description", "location", "project__name"),
        _compliance_result,
    ),
    SearchProvider("document", "公文模板", "document_search", ("name",), _document_result),
)

SOURCE_CHOICES: tuple[str, ...] = tuple(p.source for p in PROVIDERS)


def normalize_query(query: Any) -> str:
    return str(query or "").strip()[:MAX_QUERY_LENGTH]


def search_internal(
    context: Any,
    query: str,
    sources: Iterable[str] | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[dict]:
    """在内部业务模块中检索，并按调用者的 scope 过滤。

    参数:
        context: ``ToolContext``（需包含 ``user`` 与 ``scope``）
        query: 关键词（空串直接返回空列表）
        sources: 限定来源（``SOURCE_CHOICES`` 的子集）；为 None 时检索全部来源
        limit: 每个来源最多返回的条数（1..MAX_LIMIT）
    """
    query = normalize_query(query)
    if not query or context is None or getattr(context, "user", None) is None:
        return []
    try:
        limit = max(1, min(int(limit), MAX_LIMIT))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT
    wanted = set(sources) if sources else None

    results: list[dict] = []
    for provider in PROVIDERS:
        if wanted is not None and provider.source not in wanted:
            continue
        try:
            results.extend(provider.search(context, query, limit))
        except Exception:
            # 单个来源失败不影响其他来源；失败时关闭，不做任何兜底查询
            logger.warning("Internal search provider failed: source=%s", provider.source, exc_info=True)
    return results
