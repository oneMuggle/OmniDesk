"""S3 写工具基类：统一 dry_run / confirmed 分派与返回结构。

子类实现：
- ``FIELDS``：参数名 → 中文说明（用于 LLM 抽取与 schema 描述）
- ``dry_run(user, params, ctx)``：只读数据库，返回 ``self.draft(preview, fields)`` 或 ``self.fail(...)``
- ``confirm(user, fields, ctx)``：在事务中加锁、校验、执行、写日志，返回 ``self.done(...)`` 或 ``self.fail(...)``

约定：
- 确认阶段只使用 dry_run 存下的 ``fields``（含目标主键与版本），不再重新解析原话。
- 冲突类失败使用 ``error_code``：``stale_confirmation`` / ``booking_conflict`` /
  ``state_conflict``，确认接口据此返回 409。
"""

from __future__ import annotations

from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .base import RISK_LEVEL_WRITE, BaseTool

STALE_MESSAGE = "确认内容已过期（目标已被修改），请重新发起"


def parse_local_datetime(value) -> datetime | None:
    """解析 ``YYYY-MM-DDTHH:MM[:SS]``（也接受空格分隔）；无时区时按当前时区处理。"""
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = parse_datetime(value.strip().replace(" ", "T", 1))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "—"
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


class ConfirmedWriteTool(BaseTool):
    risk_level = RISK_LEVEL_WRITE
    require_confirmation = True

    #: 参数名 → 中文说明
    FIELDS: dict[str, str] = {}
    #: LLM 抽取时的任务名
    TASK_LABEL: str = ""

    # ---- 分派 -------------------------------------------------------------
    def execute(self, query=None, context=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else (vars(context) if context is not None else {})
        user = ctx.get("user") if isinstance(ctx, dict) else None
        if user is None and context is not None and not isinstance(context, dict):
            user = getattr(context, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return self.fail("未登录用户无法执行该操作")
        if ctx.get("dry_run"):
            params = self.resolve_params(query, ctx)
            if params is None:
                return self.fail(f"没能理解要{self.TASK_LABEL or '执行的操作'}的具体内容，请说得更明确一些")
            return self.dry_run(user, params, ctx)
        if ctx.get("confirmed"):
            fields = ctx.get("draft") if isinstance(ctx.get("draft"), dict) else {}
            if not fields:
                return self.fail("确认内容缺失，请重新发起", code="stale_confirmation")
            return self.confirm(user, fields, ctx)
        return self.fail("工具执行异常:未进入 dry_run 或 confirmed 模式")

    def resolve_params(self, query, ctx) -> dict | None:
        """优先使用原生函数调用给出的结构化参数，否则用 LLM 从原话抽取。"""
        params = ctx.get("params") if isinstance(ctx.get("params"), dict) else None
        if params and any(params.get(key) not in (None, "", []) for key in self.FIELDS):
            return {key: params.get(key) for key in self.FIELDS}
        from ..extractors.write_fields_extractor import extract_fields

        return extract_fields(query or "", task=self.TASK_LABEL, fields=self.FIELDS)

    # ---- 子类实现 ---------------------------------------------------------
    def dry_run(self, user, params: dict, ctx: dict) -> dict:  # pragma: no cover - 抽象
        raise NotImplementedError

    def confirm(self, user, fields: dict, ctx: dict) -> dict:  # pragma: no cover - 抽象
        raise NotImplementedError

    # ---- 返回结构 ---------------------------------------------------------
    @staticmethod
    def fail(message: str, code: str | None = None) -> dict:
        result = {"found": False, "message": message}
        if code:
            result["error_code"] = code
        return result

    @staticmethod
    def draft(preview: dict, fields: dict) -> dict:
        return {"found": True, "draft": {"summary": preview.get("action", ""), "preview": preview, "fields": fields}}

    @staticmethod
    def done(summary: str, write_log, *, reversible: bool = True, **extra) -> dict:
        return {
            "found": True,
            "summary": summary,
            "result": {"write_log_id": write_log.pk, "reversible": reversible, **extra},
        }

    # ---- schema -----------------------------------------------------------
    @classmethod
    def build_schema(cls, description: str, properties: dict) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "用户原话（用于审计）"},
                        **properties,
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }
