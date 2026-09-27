"""跨模块检索工具（只读）。

复用 ``search_federation.providers.search_internal``：数据范围由各 provider
绑定的原工具 scope 保证（SELF / DEPARTMENT / GLOBAL），本工具不直接访问模型，
因此不实现 ``build_base_queryset``（``supports_scope_filter`` 为 False，由执行器
走普通 ``execute(query, params, context)`` 分支）。
"""

from __future__ import annotations

from typing import Any

from smart_assistant.scope import resolve_scope

from .base import BaseTool
from .tool_context import ToolContext

# 与 search_federation.providers.SOURCE_CHOICES 保持一致（由测试守护）
SOURCE_ENUM = ["project", "memo", "personnel", "compliance", "document"]


def _to_tool_context(context: Any) -> ToolContext | None:
    """把 ToolContext 或旧路径 dict 上下文统一为 ToolContext；无服务端用户则返回 None。"""
    if isinstance(context, ToolContext):
        return context if context.user is not None else None
    if isinstance(context, dict):
        user = context.get("user")
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        return ToolContext(user=user, scope=resolve_scope(user))
    return None


class GlobalSearchTool(BaseTool):
    name = "global_search"
    description = "跨模块检索项目、备忘录、人员、合规问题、公文模板（按当前用户权限范围）"
    intent_type = "global_search"
    risk_level = "read"

    def execute(self, query=None, context=None, params=None, **_kwargs) -> dict:
        from search_federation.providers import search_internal

        params = params if isinstance(params, dict) else {}
        keyword = str(params.get("query") or query or "").strip()
        if not keyword:
            return {"found": False, "message": "请提供要检索的关键词"}

        tool_context = _to_tool_context(context)
        if tool_context is None:
            return {"found": False, "message": "未识别到当前用户，无法检索"}

        sources = params.get("sources")
        if isinstance(sources, list):
            sources = [s for s in sources if s in SOURCE_ENUM] or None
        else:
            sources = None

        results = search_internal(tool_context, keyword, sources=sources)
        if not results:
            return {"found": False, "message": f'未找到与 "{keyword}" 相关的内容'}

        grouped: dict[str, int] = {}
        for item in results:
            grouped[item["source"]] = grouped.get(item["source"], 0) + 1
        return {
            "found": True,
            "count": len(results),
            "by_source": grouped,
            "results": results,
        }

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "跨模块检索：一次查询项目、备忘录、人员、合规问题、公文模板，"
                    "仅返回当前用户有权查看的记录（标题、摘要、跳转链接）。"
                    "适合'帮我找一下和XX有关的内容'这类不确定模块的问题；"
                    "已明确模块时优先使用对应的专用工具。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "检索关键词",
                        },
                        "sources": {
                            "type": "array",
                            "items": {"type": "string", "enum": SOURCE_ENUM},
                            "description": "限定检索来源（可选，缺省检索全部）",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }
