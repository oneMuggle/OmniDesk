"""smart_assistant.tools.memo_write_tools — 备忘录写工具(PR1:create)

PR1 范围:仅 MemoCreateTool。PR2 在新文件 memo_write_tools_v2.py(避免破坏 PR1 评审闭环)
补 MemoUpdateTool / MemoDeleteTool;文件名待 PR2 plan 决定(可能拆/合)。

业务逻辑复用 memos.Memo 模型,通过 ORM 直接 create,跳过 MemoViewSet
(后者面向 HTTP,工具层走 ORM 更轻便)。
工具层只负责:
1. 自然语言解析(query → CreateParams)
2. dry_run 模式下返回 draft(供 confirm-replay 框架存缓存)
3. confirmed 模式下调用业务逻辑落库

上游依赖:
- confirm-replay 框架:Reference docs/plans/2026-08-04_sa-confirm-framework.md
- smart_assistant.extractors.memo_extractor.extract_create_params(LLM 解析)
- memos.models.Memo(数据落库目标)
"""
from __future__ import annotations

from django.db import transaction

from .base import BaseTool
from ..extractors.memo_extractor import extract_create_params
from memos.models import Memo

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


class MemoCreateTool(BaseTool):
    """基于自然语言创建备忘录(write, require_confirmation=True)

    复用 confirm-replay 框架:dry_run → 用户确认 → confirmed 落库。
    """

    name = "memo_create"
    description = "基于自然语言创建一条备忘录/便签(支持设置提醒时间)"
    intent_type = "memo_create"
    risk_level = "write"
    require_confirmation = True

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 创建备忘录。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "基于自然语言创建一条备忘录/便签(写操作,需要用户确认)。"
                    "dry_run 返回 draft,用户确认后真正落库。"
                    "示例 query: '帮我记一条下午开会的备忘'、"
                    "'提醒明天早上 9 点提交周报'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言描述,含标题/内容/可选提醒时间",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def execute(self, query=None, ctx=None, **kwargs) -> dict:
        """执行备忘录创建(双调用模式:dry_run / confirmed)。"""
        ctx_dict = ctx if isinstance(ctx, dict) else {}

        if ctx_dict.get("dry_run"):
            return self._dry_run(query, ctx_dict)

        if ctx_dict.get("confirmed"):
            return self._confirmed(query, ctx_dict)

        # 兜底(理论上不可达:orchestrator 会拦截)
        return {"found": False, "message": "工具执行异常:未进入 dry_run 或 confirmed 模式"}

    def _dry_run(self, query, ctx) -> dict:
        user = ctx.get("user")
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法创建备忘录"}

        params = extract_create_params(query or "")
        if params is None:
            return {"found": False, "message": "无法识别备忘内容,请明确想记什么"}

        draft = {
            "summary": f"将创建备忘录: 《{params.title}》",
            "fields": {
                "title": params.title,
                "content": params.content,
                "reminder_time": params.reminder_time,
            },
        }
        if params.reminder_time:
            draft["summary"] += f", 提醒时间 {params.reminder_time}"

        return {"found": True, "draft": draft}

    def _confirmed(self, query, ctx) -> dict:
        user = ctx.get("user")
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法创建备忘录"}

        params = extract_create_params(query or "")
        if params is None:
            return {"found": False, "message": "无法识别备忘内容"}

        try:
            with transaction.atomic():
                memo = Memo.objects.create(
                    user=user,
                    title=params.title,
                    content=params.content,
                    reminder_time=params.reminder_time or None,
                )
        except Exception as e:
            logger.warning("memo_create 落库失败: %s", e)
            return {"found": False, "message": f"创建备忘录失败: {e!s}"}

        logger.info(
            "memo_create.persisted",
            extra={
                "event": "memo_create.persisted",
                "memo_id": memo.id,
                "user_id": user.id,
            },
        )

        return {
            "found": True,
            "result": {
                "memo_id": memo.id,
                "title": memo.title,
                "reminder_time": str(memo.reminder_time) if memo.reminder_time else None,
            },
            "summary": f"已创建备忘录《{memo.title}》",
        }

    def build_base_queryset(self):
        """返回未过滤的备忘录 QuerySet(跨模块汇总路径使用)。"""
        return Memo.objects.select_related("user").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 名下的备忘录。"""
        return qs.filter(user=ctx.user)