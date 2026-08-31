from __future__ import annotations

from collections.abc import Callable
from typing import Any
import re

from uuid import uuid4

from .base import BaseTool
from smart_assistant.scope import resolve_scope

_SCOPE_RANK = {"self": 0, "department": 1, "global": 2}
_SENSITIVE_RE = re.compile(r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|1[3-9]\d{9}|\d{15}(?:\d{2}[0-9Xx])?)")
_MAX_CONTENT_LENGTH = 10_000


_SENSITIVE_KEYS = {
    "args",
    "arguments",
    "credentials",
    "credential",
    "token",
    "password",
    "secret",
    "prompt",
    "internal_prompt",
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "access_key",
    "private_key",
    "session",
    "email",
    "phone",
    "phone_number",
    "身份证",
    "身份证号",
    "id_card",
    "idcard",
}
_SENSITIVE_CANONICAL_KEYS = {re.sub(r"[^a-z0-9]", "", key.lower()) for key in _SENSITIVE_KEYS}
_SENSITIVE_CANONICAL_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"(?:^|prompt)(?:text|value)?$",
        r"credential(?:blob)?$",
        r"token(?:value)?$",
        r"bearertoken$",
        r"clientsecret$",
        r"apikey$",
        r"accesstoken$",
        r"authorizationheader$",
        r"sessionid$",
    )
)


def _is_sensitive_key(key):
    canonical = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return canonical in _SENSITIVE_CANONICAL_KEYS or any(
        pattern.search(canonical) for pattern in _SENSITIVE_CANONICAL_PATTERNS
    )


_SECRET_LIKE_RE = re.compile(r"(?i)\b(?:api[_ -]?key|credential|token|password|secret)\s*=\s*[^\s;，。]+")


def _safe_text(value: str) -> str:
    return _SENSITIVE_RE.sub("[已脱敏]", value)


def _safe_summary_title(value: str) -> str:
    value = _SECRET_LIKE_RE.sub("[已隐藏]", _safe_text(value[:80]))
    return value[:80]


def _sanitize_value(value: Any, depth: int = 0) -> Any:
    """在审计事件构造前递归过滤敏感字段及 PII。"""
    if isinstance(value, str):
        return _safe_text(value[:2000])
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if depth >= 4:
        return "[已隐藏]"
    if isinstance(value, list):
        return [_sanitize_value(item, depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        return {
            str(key): _sanitize_value(item, depth + 1)
            for key, item in list(value.items())[:30]
            if not _is_sensitive_key(key)
        }
    return "[已隐藏]"


def _sanitize_audit_payload(payload: dict) -> dict:
    return _sanitize_value(payload)


def _validate_text(values):
    title = values.get("title")
    content = values.get("content")
    if not isinstance(title, str) or not title.strip() or not isinstance(content, str) or not content.strip():
        return None, "title 和 content 不能为空"
    title, content = title.strip(), content.strip()
    if (
        len(title) > 200
        or len(content) > _MAX_CONTENT_LENGTH
        or any(ord(c) < 32 and c not in "\n\r\t" for c in title + content)
    ):
        return None, "通知标题或正文长度/格式无效"
    return {**values, "title": title, "content": content}, None


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
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "recipients": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "收件人姓名或用户名",
                        },
                        "title": {"type": "string", "description": "通知标题"},
                        "content": {"type": "string", "description": "通知内容"},
                        "scope": {
                            "type": "string",
                            "enum": ["self", "department", "global"],
                            "description": "权限范围",
                        },
                    },
                    "required": ["recipients", "title", "content", "scope"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def execute(self, query=None, context=None, params=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else {}
        if context is not None and not isinstance(context, dict):
            ctx = {
                "user": getattr(context, "user", None),
                "event_bus": getattr(context, "event_bus", None),
                "confirmed": getattr(context, "confirmed", False),
                "draft": getattr(context, "draft", None),
            }
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

    def _validate_users_scope(self, users, actor, requested_scope):
        """确认阶段按当前收件人对象重新执行范围闸门。"""
        for user in users:
            if requested_scope == "self" and user.id != actor.id:
                return "收件人超出当前范围"
            if requested_scope == "department":
                actor_department = getattr(getattr(actor, "personnel", None), "department", None)
                user_department = getattr(getattr(user, "personnel", None), "department", None)
                if not actor_department or actor_department != user_department:
                    return "收件人超出当前部门范围"
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
        values, error = _validate_text(values)
        if error:
            return {"found": False, "message": error}
        error = self._validate_scope(values["scope"], ctx, context)
        if error:
            return {"found": False, "message": error}
        users, error = self._resolve_recipients(values["recipients"], actor, values["scope"])
        if error:
            return {"found": False, "message": error}
        operation_id = str(uuid4())
        safe_title = _safe_summary_title(values["title"])
        return {
            "found": True,
            "draft": {
                "summary": f"待执行站内通知（操作：agent_notify；收件人数：{len(users)}；标题：{safe_title}）",
                "fields": {
                    "recipient_ids": [u.id for u in users],
                    "recipient_names": [u.get_full_name() or u.username for u in users],
                    "title": values["title"],
                    "content": values["content"],
                    "scope": values["scope"],
                    "operation_id": operation_id,
                },
            },
        }

    def _confirmed(self, values, ctx, context):
        actor = self._user(ctx, context)
        if actor is None or not getattr(actor, "is_authenticated", False):
            return {"found": False, "message": "未登录用户无法发送通知"}
        fields = ctx.get("draft") if isinstance(ctx.get("draft"), dict) else values
        fields = fields.get("fields", fields) if isinstance(fields, dict) else {}
        ids = fields.get("recipient_ids")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 10 or len(set(ids)) != len(ids):
            return {"found": False, "message": "确认草稿中的收件人无效"}
        users = ctx.get("_resolved_users") or (ctx.get("draft") or {}).get("_resolved_users")
        if not isinstance(users, list):
            from django.contrib.auth import get_user_model

            users = list(get_user_model().objects.filter(id__in=ids))
        users_by_id = {user.id: user for user in users}
        users = [users_by_id[user_id] for user_id in ids if user_id in users_by_id]
        if len(users) != len(ids):
            return {"found": False, "message": "确认草稿中的收件人不存在"}
        required = ("title", "content", "scope")
        if any(not isinstance(fields.get(key), str) or not fields[key].strip() for key in required):
            return {"found": False, "message": "确认草稿缺少有效的 title、content 或 scope"}
        fields = {
            **fields,
            "title": fields["title"].strip(),
            "content": fields["content"].strip(),
            "scope": fields["scope"].strip(),
        }
        fields, error = _validate_text(fields)
        if error:
            return {"found": False, "message": error}
        error = self._validate_scope(fields.get("scope"), ctx, context)
        if error:
            return {"found": False, "message": error}
        error = self._validate_users_scope(users, actor, fields["scope"])
        if error:
            return {"found": False, "message": error}
        from notifications.channels import resolve_channels

        operation_id = fields.get("operation_id") or ctx.get("operation_id") or str(uuid4())
        sent = []
        failed = []
        for user in users:
            channels = resolve_channels(user, "agent_notify")
            if not channels:
                failed.append({"user_id": user.id, "channel": "unavailable", "reason": "no_channel"})
                continue
            for channel in channels:
                try:
                    result = channel.send(
                        user=user,
                        type="agent_notify",
                        title=fields["title"],
                        content=fields["content"],
                        dedupe_key=f"agent_notify:{operation_id}:{user.id}",
                    )
                    if result.success:
                        sent.append(
                            {"user_id": user.id, "channel": getattr(channel, "name", channel.__class__.__name__)}
                        )
                    else:
                        failed.append(
                            {
                                "user_id": user.id,
                                "channel": getattr(channel, "name", channel.__class__.__name__),
                                "reason": "send_failed",
                            }
                        )
                except Exception:
                    failed.append(
                        {
                            "user_id": user.id,
                            "channel": getattr(channel, "name", channel.__class__.__name__),
                            "reason": "send_failed",
                        }
                    )
        audit_channels = list(dict.fromkeys(item["channel"] for item in [*sent, *failed] if item.get("channel")))
        audit_payload_data = {
            "operation_id": operation_id,
            "phase": "notify",
            "sent_count": len(sent),
            "failed_count": len(failed),
            "recipient_count": len(users),
            "channels": audit_channels,
            "sent": [{"channel": item["channel"]} for item in sent],
            "failed": [{"channel": item["channel"], "reason": item["reason"]} for item in failed],
        }
        if len(audit_channels) == 1:
            audit_payload_data["channel"] = audit_channels[0]
        audit_payload = _sanitize_audit_payload(audit_payload_data)
        event_bus = ctx.get("event_bus")
        if event_bus is not None:
            event_bus.emit(
                "subtask.tool_result",
                {**audit_payload, "phase": "notify", "operation": "agent_notify"},
            )
        if failed:
            return {
                "found": False,
                "message": "部分通知发送失败",
                "result": {
                    "operation_id": operation_id,
                    "sent": sent,
                    "failed": failed,
                    "sent_count": len(sent),
                    "failed_count": len(failed),
                    "recipient_count": len(users),
                },
            }
        return {
            "found": True,
            "result": {
                "operation_id": operation_id,
                "sent_count": len(sent),
                "failed_count": 0,
                "recipient_count": len(users),
                "sent": sent,
                "failed": [],
            },
            "summary": f"已发送 {len(users)} 条站内通知",
        }


AgentNotifyTool = NotifyTool
