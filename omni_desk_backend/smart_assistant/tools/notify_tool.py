from __future__ import annotations

from typing import Any, Callable

from .base import BaseTool
from notifications.channels import resolve_channel
from smart_assistant.scope import SmartAssistantScope, resolve_scope

_SCOPE_RANK = {"self": 0, "department": 1, "global": 2}


def _default_resolver(name: str, _actor: Any) -> list[Any]:
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()
    return list(User.objects.filter(Q(username=name) | Q(real_name=name) | Q(personnel__name=name)).distinct())


class NotifyTool(BaseTool):
    name = "agent_notify"
    description = "向一个或多个用户发送站内通知(写操作,需要用户确认)。"
    intent_type = "agent_notify"
    risk_level = "write"
    require_confirmation = True
    required_auth = True

    def __init__(self, resolver: Callable[[str, Any], list[Any]] | None = None):
        self.resolver = resolver or _default_resolver

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        return {"type": "function", "function": {"name": cls.name, "description": cls.description, "parameters": {"type": "object", "properties": {"recipients": {"type": "array", "items": {"type": "string"}, "description": "收件人姓名或用户名"}, "title": {"type": "string", "description": "通知标题"}, "content": {"type": "string", "description": "通知内容"}, "scope": {"type": "string", "enum": ["self", "department", "global"], "description": "权限范围"}}, "required": ["recipients", "title", "content", "scope"], "additionalProperties": False}, "strict": True}}

    def execute(self, query=None, context=None, params=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else {}
        if context is not None and not isinstance(context, dict):
            ctx = {"user": getattr(context, "user", None)}
        values = params if isinstance(params, dict) else (query if isinstance(query, dict) else {})
        if isinstance(query, str):
            import json
            try:
                values = json.loads(query)
            except (TypeError, ValueError):
                values = {}
        if not isinstance(values, dict):
            return {"found": False, "message": "通知参数必须是对象"}
        if "scope" not in values:
            values = dict(values)
            values["scope"] = self._context_scope(ctx, context)
        if ctx.get("dry_run") or values.get("dry_run"):
            return self._dry_run(values, ctx, context)
        if ctx.get("confirmed") or values.get("confirmed"):
            return self._confirmed(values, ctx, context)
        return {"found": False, "message": "工具执行异常:未进入 dry_run 或 confirmed 模式"}

    @staticmethod
    def _user(ctx, context):
        return ctx.get("user") or getattr(context, "user", None)

    @staticmethod
    def _context_scope(ctx, context):
        user = NotifyTool._user(ctx, context)
        derived = resolve_scope(user)
        return derived.value

    def _validate_scope(self, requested, ctx, context):
        if requested not in _SCOPE_RANK:
            return "scope 必须是 self、department 或 global"
        if _SCOPE_RANK[requested] > _SCOPE_RANK.get(self._context_scope(ctx, context), 0):
            return f"scope 超出当前权限: {requested}"
        return None

    def _resolve_recipients(self, names, actor, requested_scope):
        if not isinstance(names, list) or not names:
            return None, "收件人数量必须在 1 到 10 人之间"
        unique_names = list(dict.fromkeys(names))
        if len(unique_names) > 10:
            return None, "收件人数量不能超过 10 人"
        users = []
        seen_ids = set()
        for name in unique_names:
            candidates = self.resolver(name, actor)
            if len(candidates) == 0:
                return None, f"未找到收件人 '{name}'"
            if len(candidates) > 1:
                return None, f"收件人 '{name}' 匹配到多个候选,请明确指定"
            user = candidates[0]
            if user.id in seen_ids:
                continue
            if requested_scope == "self" and user.id != actor.id:
                return None, "收件人超出当前范围"
            if requested_scope == "department":
                actor_department = getattr(getattr(actor, "personnel", None), "department", None)
                user_department = getattr(getattr(user, "personnel", None), "department", None)
                if not actor_department or actor_department != user_department:
                    return None, "收件人超出当前部门范围"
            users.append(user)
            seen_ids.add(user.id)
        if not users:
            return None, "收件人数量必须在 1 到 10 人之间"
        return users, None

    def _dry_run(self, values, ctx, context):
        actor = self._user(ctx, context)
        if actor is None or not getattr(actor, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法发送通知"}
        if any(not values.get(key) for key in ("recipients", "title", "content", "scope")):
            return {"found": False, "message": "recipients、title、content、scope 均为必填"}
        error = self._validate_scope(values["scope"], ctx, context)
        if error:
            return {"found": False, "message": error}
        users, error = self._resolve_recipients(values["recipients"], actor, values["scope"])
        if error:
            return {"found": False, "message": error}
        return {"found": True, "draft": {"summary": f"向 {len(users)} 人发送通知: {values['title']}", "fields": {"recipient_ids": [u.id for u in users], "title": values["title"], "content": values["content"], "scope": values["scope"]}}}

    def _confirmed(self, values, ctx, context):
        actor = self._user(ctx, context)
        if actor is None or not getattr(actor, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法发送通知"}
        fields = ctx.get("draft") if isinstance(ctx.get("draft"), dict) else values
        fields = fields.get("fields", fields) if isinstance(fields, dict) else {}
        ids = fields.get("recipient_ids")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 10 or len(set(ids)) != len(ids):
            return {"found": False, "message": "确认草稿中的收件人无效"}
        from django.contrib.auth import get_user_model
        users = list(get_user_model().objects.filter(id__in=ids))
        users_by_id = {user.id: user for user in users}
        users = [users_by_id[user_id] for user_id in ids if user_id in users_by_id]
        if len(users) != len(ids):
            return {"found": False, "message": "确认草稿中的收件人不存在"}
        required = ("title", "content", "scope")
        if any(not isinstance(fields.get(key), str) or not fields[key].strip() for key in required):
            return {"found": False, "message": "确认草稿缺少有效的 title、content 或 scope"}
        error = self._validate_scope(fields.get("scope"), ctx, context)
        if error:
            return {"found": False, "message": error}
        for user in users:
            result = resolve_channel(user, "agent_notify").send(user=user, type="agent_notify", title=fields["title"], content=fields["content"])
            if not result.success:
                return {"found": False, "message": result.message or "通知发送失败"}
        return {"found": True, "result": {"sent_count": len(users)}, "summary": f"已发送 {len(users)} 条站内通知"}


AgentNotifyTool = NotifyTool
