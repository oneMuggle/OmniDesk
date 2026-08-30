"""smart_assistant.tools.memo_write_tools — 备忘录写工具(PR1:create)

PR1 范围:仅 MemoCreateTool。PR2 在新文件 memo_write_tools_v2.py(避免破坏 PR1 评审闭环)
补 MemoUpdateTool / MemoDeleteTool;文件名待 PR2 plan 决定(可能拆/合)。

业务逻辑复用 memos.Memo 模型,通过 ORM 直接 create,跳过 MemoViewSet
(后者面向 HTTP,工具层走 ORM 更轻便)。
工具层只负责:
1. 自然语言解析(query → CreateParams)
2. dry_run 模式下返回 draft(供 confirm-replay 框架存缓存)
3. confirmed 模式下调用业务逻辑落库

调用契约:execute 签名与框架一致 —— ``execute(query=None, context=None, **kwargs)``,
框架所有调用点(orchestrator / chat.py replay / tool_chain_executor)都以 ``context=``
关键字传参,经 ``execute_guarded`` 原样透传。context 可为 dict 或 ToolContext 实例。

上游依赖:
- confirm-replay 框架:Reference docs/plans/2026-08-04_sa-confirm-framework.md
- smart_assistant.extractors.memo_extractor.extract_create_params(LLM 解析)
- memos.models.Memo(数据落库目标)
"""

from __future__ import annotations

from datetime import datetime

from django.db import transaction

from .base import BaseTool
from ..extractors.memo_extractor import CreateParams, extract_create_params
from memos.models import Memo
from smart_assistant.models import AgentWriteLog

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


def _parse_reminder_time(s: str) -> datetime | None:
    """鲁棒地解析提醒时间字符串,失败返回 None。

    接受格式:
    - "2026-08-12T15:00:00"(ISO datetime)
    - "2026-08-12T15:00"(ISO datetime 无秒)
    - "2026-08-12 15:00:00"(空格分隔)
    - "2026-08-12"(date-only,默认当日 00:00)

    返回 aware datetime(按 settings.TIME_ZONE),消除 USE_TZ=True 下
    落库 naive datetime 的 RuntimeWarning。
    """
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            break
        except ValueError:
            continue
    else:
        logger.debug(
            "smart_assistant.memo_write_tools.reminder_time_parse_failed",
            extra={"event": "smart_assistant.memo_write_tools.reminder_time_parse_failed", "s": s},
        )
        return None
    from django.utils import timezone

    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


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

    def execute(self, query=None, context=None, **kwargs) -> dict:
        """执行备忘录创建(双调用模式 + 兜底)。

        - dry_run:返回 draft(供 confirm-replay 框架存缓存)
        - confirmed:真正落库
        - 兜底:防御性兜底(测试显式覆盖),正常流程被 orchestrator 拦截
        """
        ctx = context if isinstance(context, dict) else (vars(context) if context is not None else {})

        if ctx.get("dry_run"):
            return self._dry_run(query, ctx, context)

        if ctx.get("confirmed"):
            return self._confirmed(query, ctx, context)

        # 防御性兜底(正常流程不可达:orchestrator 会先走 dry_run/confirmed)
        return {"found": False, "message": "工具执行异常:未进入 dry_run 或 confirmed 模式"}

    def _resolve_user(self, ctx, context):
        """解析当前用户:优先 ctx dict,其次 ToolContext 实例;缺失返回 None。"""
        user = ctx.get("user") if isinstance(ctx, dict) else None
        if user is None and context is not None:
            user = getattr(context, "user", None)
        return user

    def _dry_run(self, query, ctx, context=None) -> dict:
        user = self._resolve_user(ctx, context)
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法创建备忘录(上下文缺失 user)"}

        params = extract_create_params(query or "")
        if params is None:
            return {"found": False, "message": "无法识别备忘内容,请明确想记什么"}

        if params.reminder_time and _parse_reminder_time(params.reminder_time) is None:
            return {
                "found": False,
                "message": f"无法解析提醒时间 '{params.reminder_time}',请确认时间格式",
            }

        summary = f"将创建备忘录: 《{params.title}》"
        if params.reminder_time:
            summary += f", 提醒时间 {params.reminder_time}"
        draft = {
            "summary": summary,
            "fields": {
                "title": params.title,
                "content": params.content,
                "reminder_time": params.reminder_time,
            },
        }

        return {"found": True, "draft": draft}

    def _resolve_params(self, query, ctx) -> CreateParams | None:
        """优先使用框架注入的 draft fields,缺失时回退 LLM 提取。

        chat.py replay 路径注入 ``draft=f"{fields}"``,此时不二次调 LLM
        (避免 2-4s 延迟 + LLM 非确定性导致落库内容与用户确认漂移)。
        """
        draft_fields = ctx.get("draft") if isinstance(ctx, dict) else None
        if isinstance(draft_fields, dict):
            title = draft_fields.get("title")
            if isinstance(title, str) and title:
                return CreateParams(
                    title=title,
                    content=draft_fields.get("content") or "",
                    reminder_time=draft_fields.get("reminder_time"),
                )
        return extract_create_params(query or "")

    def _confirmed(self, query, ctx, context=None) -> dict:
        user = self._resolve_user(ctx, context)
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法创建备忘录(上下文缺失 user)"}

        params = self._resolve_params(query, ctx)
        if params is None:
            return {"found": False, "message": "无法识别备忘内容"}

        reminder_time = _parse_reminder_time(params.reminder_time) if params.reminder_time else None

        try:
            with transaction.atomic():
                memo = Memo.objects.create(
                    user=user,
                    title=params.title,
                    content=params.content,
                    reminder_time=reminder_time,
                )
                task = None
                task_id = ctx.get("task_id")
                if task_id:
                    from smart_assistant.models import AgentTask
                    task = AgentTask.objects.filter(task_id=task_id, user=user).first()
                    if task is None:
                        raise ValueError("任务不存在或不属于当前用户")
                AgentWriteLog.objects.create(
                    task=task, session_id=ctx.get("session_id"), user=user,
                    tool_name=ctx.get("tool_name") or self.intent_type, target_model="memos.Memo",
                    target_pk=str(memo.pk), operation="create", before=None,
                    after={"title": memo.title, "content": memo.content, "reminder_time": str(memo.reminder_time) if memo.reminder_time else None, "is_deleted": False, "deleted_at": None},
                )
        except Exception as e:
            logger.warning(
                "memo_create.persist_failed",
                extra={
                    "event": "memo_create.persist_failed",
                    "user_id": getattr(user, "id", None),
                    "error": str(e),
                },
            )
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
        """返回未过滤的备忘录 QuerySet。

        供只读/汇总路径兼容使用的接口;写工具当前不被 scope 路由调用
        (execute 走 confirm-replay,不经跨模块汇总 scope 分发)。
        """
        return Memo.objects.select_related("user").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 名下的备忘录(user 缺失时返回空集)。"""
        user = getattr(ctx, "user", None)
        if user is None:
            return qs.none()
        return qs.filter(user=user)
