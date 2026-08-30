"""smart_assistant.tools.memo_write_tools_v2 — 备忘录写工具 v2(PR2:update + delete)

PR1 的 MemoCreateTool 在 memo_write_tools.py;PR2 新增 MemoUpdateTool /
MemoDeleteTool 放本文件(PR1 已预留文件名)。共享 _parse_reminder_time(from
memo_write_tools)与 _find_candidates(本文件模块级)。

定位策略:LLM 提取 target_title → user + title__icontains 匹配。
dry_run 多候选(>1 条)直接拒绝,防止误改/误删;draft fields 携带
memo_id + target_title,confirmed 按 memo_id(校验 user 归属)优先定位,
回退标题重定位。

安全约定(定位/归属失败直接拒绝):confirmed 阶段若 memo_id 已携带但归属
校验失败(非本人或已删除),直接返回 found=False,绝不静默回退到标题重定位
—— 防止把用户已确认的 memo 悄悄替换成同标题的其他记录(安全性优先)。
memo_id 缺失时才允许标题重定位,且要求恰 1 个候选。
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .base import BaseTool
from .memo_write_tools import _parse_reminder_time
from ..extractors.memo_update_extractor import UpdateParams, extract_update_params
from ..extractors.memo_delete_extractor import extract_delete_params
from memos.models import Memo
from smart_assistant.models import AgentWriteLog

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


def _find_candidates(user, target_title: str):
    """按标题关键词返回用户名下的备忘录(创建时间倒序,取最近 5 条)。"""
    qs = Memo.objects.filter(user=user)
    if target_title:
        qs = qs.filter(title__icontains=target_title)
    return qs.order_by("-created_at")[:5]


class MemoUpdateTool(BaseTool):
    """基于自然语言修改一条已有备忘录(write, require_confirmation=True)。"""

    name = "memo_update"
    description = "基于自然语言修改一条已有备忘录/便签(支持改标题、内容、提醒时间)"
    intent_type = "memo_update"
    risk_level = "write"
    require_confirmation = True

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "基于自然语言修改一条已有备忘录(写操作,需要用户确认)。"
                    "dry_run 返回 draft,用户确认后真正落库。"
                    "示例 query: '把明天开会的备忘改成后天下午3点'、"
                    "'修改买菜备忘的标题为采购清单'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言描述,含目标备忘录与要修改的内容",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def execute(self, query=None, context=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else (vars(context) if context is not None else {})

        if ctx.get("dry_run"):
            return self._dry_run(query, ctx, context)

        if ctx.get("confirmed"):
            return self._confirmed(query, ctx, context)

        return {"found": False, "message": "工具执行异常:未进入 dry_run 或 confirmed 模式"}

    def _resolve_user(self, ctx, context):
        user = ctx.get("user") if isinstance(ctx, dict) else None
        if user is None and context is not None:
            user = getattr(context, "user", None)
        return user

    def _resolve_params(self, query, ctx) -> UpdateParams | None:
        """优先使用框架注入的 draft fields,缺失时回退 LLM 提取。"""
        draft_fields = ctx.get("draft") if isinstance(ctx, dict) else None
        if isinstance(draft_fields, dict) and draft_fields.get("target_title"):
            return UpdateParams(
                target_title=draft_fields.get("target_title"),
                new_title=draft_fields.get("new_title"),
                new_content=draft_fields.get("new_content"),
                new_reminder_time=draft_fields.get("new_reminder_time"),
            )
        return extract_update_params(query or "")

    def _dry_run(self, query, ctx, context=None) -> dict:
        user = self._resolve_user(ctx, context)
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法修改备忘录(上下文缺失 user)"}

        params = extract_update_params(query or "")
        if params is None:
            return {"found": False, "message": "无法识别要修改的备忘录或修改内容"}

        if params.new_reminder_time and _parse_reminder_time(params.new_reminder_time) is None:
            return {"found": False, "message": f"无法解析提醒时间 '{params.new_reminder_time}'"}

        candidates = list(_find_candidates(user, params.target_title))
        if not candidates:
            return {"found": False, "message": f"未找到标题包含 '{params.target_title}' 的备忘录"}
        if len(candidates) > 1:
            return {"found": False, "message": f"找到 {len(candidates)} 条匹配的备忘录,请指明更精确的标题"}

        memo = candidates[0]
        changes = []
        if params.new_title:
            changes.append(f"标题→{params.new_title}")
        if params.new_content:
            changes.append(f"内容→{params.new_content}")
        if params.new_reminder_time:
            changes.append(f"提醒→{params.new_reminder_time}")

        draft = {
            "summary": f"将修改备忘录《{memo.title}》: " + "、".join(changes),
            "fields": {
                "target_title": params.target_title,
                "memo_id": memo.id,
                "new_title": params.new_title,
                "new_content": params.new_content,
                "new_reminder_time": params.new_reminder_time,
                "version": memo.updated_at.isoformat(),
            },
        }
        return {"found": True, "draft": draft}

    def _locate(self, user, params, fields) -> Memo | None:
        """优先按 draft 的 memo_id(校验 user 归属),缺失时回退按 target_title 重定位。

        定位/归属失败直接拒绝:仅当 memo_id 缺失时才回退标题重定位(要求恰 1 个候选)。
        memo_id 已携带但归属校验失败(非本人或已删除)时直接返回 None,绝不静默
        回退标题 —— 防止把用户已确认的 memo 悄悄替换成同标题的其他记录(安全性优先)。
        """
        memo_id = fields.get("memo_id") if isinstance(fields, dict) else None
        if memo_id is not None:
            memo = Memo.objects.filter(id=memo_id, user=user).first()
            if memo is not None:
                return memo
            return None
        candidates = list(_find_candidates(user, params.target_title))
        if len(candidates) != 1:
            return None
        return candidates[0]

    def _confirmed(self, query, ctx, context=None) -> dict:
        user = self._resolve_user(ctx, context)
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法修改备忘录(上下文缺失 user)"}

        params = self._resolve_params(query, ctx)
        if params is None:
            return {"found": False, "message": "无法识别要修改的备忘录"}

        memo = self._locate(user, params, ctx.get("draft") if isinstance(ctx, dict) else {})
        if memo is None:
            return {"found": False, "message": f"未找到标题包含 '{params.target_title}' 的备忘录"}

        try:
            with transaction.atomic():
                memo = Memo.all_objects.select_for_update().filter(pk=memo.pk, user=user).first()
                fields = ctx.get("draft") if isinstance(ctx, dict) else {}
                if memo is None or (fields.get("version") and memo.updated_at.isoformat() != fields["version"]):
                    return {"found": False, "error_code": "stale_confirmation", "message": "确认内容已过期，请重新确认"}
                old_title, old_content, old_reminder = memo.title, memo.content, memo.reminder_time
                if params.new_title is not None:
                    memo.title = params.new_title[:200]
                if params.new_content is not None:
                    memo.content = params.new_content
                if params.new_reminder_time is not None:
                    parsed = _parse_reminder_time(params.new_reminder_time)
                    if parsed is None:
                        return {"found": False, "message": f"无法解析提醒时间 '{params.new_reminder_time}'"}
                    memo.reminder_time = parsed
                memo.save(update_fields=["title", "content", "reminder_time", "updated_at"])
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
                    target_pk=str(memo.pk), operation="update", before={"title": old_title, "content": old_content, "reminder_time": str(old_reminder) if old_reminder else None, "is_deleted": memo.is_deleted, "deleted_at": memo.deleted_at.isoformat() if memo.deleted_at else None}, after={"title": memo.title, "content": memo.content, "reminder_time": str(memo.reminder_time) if memo.reminder_time else None, "is_deleted": memo.is_deleted, "deleted_at": memo.deleted_at.isoformat() if memo.deleted_at else None},
                )
        except Exception as e:
            logger.warning(
                "memo_update.persist_failed",
                extra={
                    "event": "memo_update.persist_failed",
                    "user_id": getattr(user, "id", None),
                    "error": str(e),
                },
            )
            return {"found": False, "message": "修改备忘录失败，请稍后重试", "error_code": "memo_update_failed"}

        logger.info(
            "memo_update.persisted",
            extra={
                "event": "memo_update.persisted",
                "memo_id": memo.id,
                "user_id": user.id,
            },
        )
        return {
            "found": True,
            "result": {"memo_id": memo.id, "title": memo.title},
            "summary": f"已更新备忘录《{memo.title}》",
        }

    def build_base_queryset(self):
        """返回未过滤的备忘录 QuerySet。

        供只读/汇总路径兼容使用的接口;写/删除工具当前不被 scope 路由调用
        (execute 走 confirm-replay,不经跨模块汇总 scope 分发)。
        """
        return Memo.objects.select_related("user").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 名下的备忘录(user 缺失时返回空集)。"""
        user = getattr(ctx, "user", None)
        if user is None:
            return qs.none()
        return qs.filter(user=user)


class MemoDeleteTool(BaseTool):
    """基于自然语言删除一条已有备忘录(destructive, require_confirmation=True)。

    破坏性操作:draft summary 显式标注"永久删除 / 不可恢复",由 confirm-replay
    框架的二次确认承担用户确认。
    """

    name = "memo_delete"
    description = "基于自然语言删除一条已有备忘录/便签(破坏性操作,需二次确认)"
    intent_type = "memo_delete"
    risk_level = "destructive"
    require_confirmation = True

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "基于自然语言删除一条已有备忘录(破坏性操作,必须用户二次确认)。"
                    "dry_run 返回 draft,用户确认后真正删除。"
                    "示例 query: '删掉明天开会的备忘'、'把采购备忘删了'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言描述,含要删除的备忘录标题关键词",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def execute(self, query=None, context=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else (vars(context) if context is not None else {})

        if ctx.get("dry_run"):
            return self._dry_run(query, ctx, context)

        if ctx.get("confirmed"):
            return self._confirmed(query, ctx, context)

        return {"found": False, "message": "工具执行异常:未进入 dry_run 或 confirmed 模式"}

    def _resolve_user(self, ctx, context):
        user = ctx.get("user") if isinstance(ctx, dict) else None
        if user is None and context is not None:
            user = getattr(context, "user", None)
        return user

    def _resolve_params(self, query, ctx):
        """优先使用框架注入的 draft fields,缺失时回退 LLM 提取。"""
        draft_fields = ctx.get("draft") if isinstance(ctx, dict) else None
        if isinstance(draft_fields, dict) and draft_fields.get("target_title"):
            from ..extractors.memo_delete_extractor import DeleteParams

            return DeleteParams(target_title=draft_fields.get("target_title"))
        return extract_delete_params(query or "")

    def _dry_run(self, query, ctx, context=None) -> dict:
        user = self._resolve_user(ctx, context)
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法删除备忘录(上下文缺失 user)"}

        params = extract_delete_params(query or "")
        if params is None:
            return {"found": False, "message": "无法识别要删除的备忘录"}

        candidates = list(_find_candidates(user, params.target_title))
        if not candidates:
            return {"found": False, "message": f"未找到标题包含 '{params.target_title}' 的备忘录"}
        if len(candidates) > 1:
            return {"found": False, "message": f"找到 {len(candidates)} 条匹配的备忘录,请指明更精确的标题"}

        memo = candidates[0]
        draft = {
            "summary": f"⚠️ 将永久删除备忘录《{memo.title}》,此操作不可恢复。确认?",
            "fields": {"target_title": params.target_title, "memo_id": memo.id, "version": memo.updated_at.isoformat()},
        }
        return {"found": True, "draft": draft}

    def _locate(self, user, params, fields) -> Memo | None:
        """优先按 draft 的 memo_id(校验 user 归属),缺失时回退按 target_title 重定位。

        定位/归属失败直接拒绝:仅当 memo_id 缺失时才回退标题重定位(要求恰 1 个候选)。
        memo_id 已携带但归属校验失败(非本人或已删除)时直接返回 None,绝不静默
        回退标题 —— 防止把用户已确认删除的 memo 悄悄替换成同标题的其他记录(安全性优先)。
        """
        memo_id = fields.get("memo_id") if isinstance(fields, dict) else None
        if memo_id is not None:
            memo = Memo.objects.filter(id=memo_id, user=user).first()
            if memo is not None:
                return memo
            return None
        candidates = list(_find_candidates(user, params.target_title))
        if len(candidates) != 1:
            return None
        return candidates[0]

    def _confirmed(self, query, ctx, context=None) -> dict:
        user = self._resolve_user(ctx, context)
        if user is None or not getattr(user, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法删除备忘录(上下文缺失 user)"}

        params = self._resolve_params(query, ctx)
        if params is None:
            return {"found": False, "message": "无法识别要删除的备忘录"}

        memo = self._locate(user, params, ctx.get("draft") if isinstance(ctx, dict) else {})
        if memo is None:
            return {"found": False, "message": f"未找到标题包含 '{params.target_title}' 的备忘录"}

        try:
            with transaction.atomic():
                memo = Memo.all_objects.select_for_update().filter(pk=memo.pk, user=user).first()
                fields = ctx.get("draft") if isinstance(ctx, dict) else {}
                if memo is None or (fields.get("version") and memo.updated_at.isoformat() != fields["version"]):
                    return {"found": False, "error_code": "stale_confirmation", "message": "确认内容已过期，请重新确认"}
                before = {"title": memo.title, "content": memo.content, "reminder_time": str(memo.reminder_time) if memo.reminder_time else None, "is_deleted": memo.is_deleted, "deleted_at": memo.deleted_at.isoformat() if memo.deleted_at else None}
                memo.is_deleted = True
                memo.deleted_at = timezone.now()
                memo.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
                task = None
                task_id = ctx.get("task_id")
                if task_id:
                    from smart_assistant.models import AgentTask
                    task = AgentTask.objects.filter(task_id=task_id, user=user).first()
                    if task is None:
                        raise ValueError("任务不存在或不属于当前用户")
                AgentWriteLog.objects.create(
                    task=task, session_id=ctx.get("session_id"), user=user,
                    tool_name=ctx.get("tool_name") or self.intent_type, target_model="memos.Memo", target_pk=str(memo.pk),
                    operation="delete", before=before, after={**before, "is_deleted": True, "deleted_at": memo.deleted_at.isoformat() if memo.deleted_at else None},
                )
        except Exception as e:
            logger.warning(
                "memo_delete.persist_failed",
                extra={
                    "event": "memo_delete.persist_failed",
                    "user_id": getattr(user, "id", None),
                    "error": str(e),
                },
            )
            return {"found": False, "message": "删除备忘录失败，请稍后重试", "error_code": "memo_delete_failed"}

        logger.info(
            "memo_delete.persisted",
            extra={
                "event": "memo_delete.persisted",
                "memo_id": memo.id,
                "user_id": user.id,
            },
        )
        return {
            "found": True,
            "result": {"memo_id": memo.id, "title": memo.title},
            "summary": f"已删除备忘录《{memo.title}》",
        }

    def build_base_queryset(self):
        """返回未过滤的备忘录 QuerySet。

        供只读/汇总路径兼容使用的接口;写/删除工具当前不被 scope 路由调用
        (execute 走 confirm-replay,不经跨模块汇总 scope 分发)。
        """
        return Memo.objects.select_related("user").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 名下的备忘录(user 缺失时返回空集)。"""
        user = getattr(ctx, "user", None)
        if user is None:
            return qs.none()
        return qs.filter(user=user)
