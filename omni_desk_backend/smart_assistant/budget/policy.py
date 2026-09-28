"""上限解析与状态计算。

- 用户上限：个人覆盖 > 所在用户组（多个组逐项取最宽松，0 = 不限最宽松）> 全员默认；
- 应用上限：``scope=app`` 那条，没有则不限；
- 状态：任一设了上限的指标用量 ≥ 上限 → blocked；≥ 软上限比例 → readonly；否则 ok。
  用户状态与应用状态取更严重的一个。

上限配置快照缓存 60 秒，``LlmBudgetPolicy`` 保存 / 删除时失效。没有任何上限时直接返回 ok，不查用量。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.core.cache import cache

from .usage import app_usage_today, user_usage_today

CACHE_KEY = "llm_budget:policies:v1"
CACHE_TIMEOUT = 60
DEFAULT_SOFT_PERCENT = 80

STATE_OK = "ok"
STATE_READONLY = "readonly"
STATE_BLOCKED = "blocked"
_SEVERITY = {STATE_OK: 0, STATE_READONLY: 1, STATE_BLOCKED: 2}

APP_LABELS = {
    "smart_assistant": "智能助手",
    "office_assistant": "办公助手",
    "file_processing": "文件处理",
    "documents": "合规报告抽取",
}


def app_label(app_name: str) -> str:
    return APP_LABELS.get(app_name, app_name)


def invalidate_cache(*_args, **_kwargs) -> None:
    cache.delete(CACHE_KEY)


def _snapshot() -> list[dict]:
    rows = cache.get(CACHE_KEY)
    if rows is None:
        from smart_assistant.models import LlmBudgetPolicy

        rows = list(
            LlmBudgetPolicy.objects.values(
                "scope",
                "group_id",
                "group__name",
                "user_id",
                "app_name",
                "daily_token_limit",
                "daily_call_limit",
                "soft_limit_percent",
            )
        )
        cache.set(CACHE_KEY, rows, CACHE_TIMEOUT)
    return rows


def soft_percent(rows: list[dict] | None = None) -> int:
    rows = _snapshot() if rows is None else rows
    for row in rows:
        if row["scope"] == "default":
            return min(100, max(1, row["soft_limit_percent"] or DEFAULT_SOFT_PERCENT))
    return DEFAULT_SOFT_PERCENT


def _has_limits(rows: list[dict]) -> bool:
    return any(row["daily_token_limit"] or row["daily_call_limit"] for row in rows)


@dataclass(frozen=True)
class Limits:
    tokens: int
    calls: int
    source: str

    @property
    def unlimited(self) -> bool:
        return not self.tokens and not self.calls


def _most_generous(values: list[int]) -> int:
    return 0 if any(v == 0 for v in values) else max(values)


def user_limits(user_id, rows: list[dict] | None = None) -> Limits:
    rows = _snapshot() if rows is None else rows
    for row in rows:
        if row["scope"] == "user" and row["user_id"] == user_id:
            return Limits(row["daily_token_limit"], row["daily_call_limit"], "个人")
    group_rows = [row for row in rows if row["scope"] == "group"]
    if group_rows and user_id:
        from django.contrib.auth import get_user_model

        group_ids = set(get_user_model().objects.filter(pk=user_id).values_list("groups", flat=True))
        matched = [row for row in group_rows if row["group_id"] in group_ids]
        if matched:
            return Limits(
                _most_generous([row["daily_token_limit"] for row in matched]),
                _most_generous([row["daily_call_limit"] for row in matched]),
                "用户组：" + "、".join(sorted(row["group__name"] or "" for row in matched)),
            )
    for row in rows:
        if row["scope"] == "default":
            return Limits(row["daily_token_limit"], row["daily_call_limit"], "全员默认")
    return Limits(0, 0, "全员默认")


def app_limits(app_name: str, rows: list[dict] | None = None) -> Limits:
    rows = _snapshot() if rows is None else rows
    for row in rows:
        if row["scope"] == "app" and row["app_name"] == app_name:
            return Limits(row["daily_token_limit"], row["daily_call_limit"], f"应用：{app_label(app_name)}")
    return Limits(0, 0, "未设置")


@dataclass
class Part:
    state: str
    usage: dict
    limits: Limits
    percent: int | None

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "usage": self.usage,
            "limits": {"tokens": self.limits.tokens, "calls": self.limits.calls, "source": self.limits.source},
            "percent": self.percent,
        }


def evaluate(usage: dict, limits: Limits, soft: int) -> Part:
    ratios = [
        usage[key] / limit for key, limit in (("tokens", limits.tokens), ("calls", limits.calls)) if limit and limit > 0
    ]
    if not ratios:
        return Part(STATE_OK, usage, limits, None)
    ratio = max(ratios)
    if ratio >= 1:
        state = STATE_BLOCKED
    elif ratio * 100 >= soft:
        state = STATE_READONLY
    else:
        state = STATE_OK
    return Part(state, usage, limits, int(ratio * 100))


@dataclass
class BudgetState:
    state: str = STATE_OK
    app_name: str = "smart_assistant"
    soft_percent: int = DEFAULT_SOFT_PERCENT
    user: Part | None = None
    app: Part | None = None
    message: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return self.state == STATE_BLOCKED

    @property
    def readonly(self) -> bool:
        return self.state in (STATE_READONLY, STATE_BLOCKED)

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "app_name": self.app_name,
            "app_label": app_label(self.app_name),
            "soft_percent": self.soft_percent,
            "message": self.message,
            "user": self.user.to_dict() if self.user else None,
            "app": self.app.to_dict() if self.app else None,
        }


def _message(state: str, user_part: Part | None, app_part: Part | None, app_name: str) -> str:
    if state == STATE_OK:
        return ""
    label = app_label(app_name)
    culprit_is_user = user_part is not None and user_part.state == state
    if state == STATE_BLOCKED:
        if culprit_is_user:
            return "你今天的 AI 额度已用完，明天 0 点自动恢复；如需调整请联系管理员。"
        return f"「{label}」今天的 AI 总额度已用完，明天 0 点自动恢复；如需调整请联系管理员。"
    who = "你今天的 AI 额度" if culprit_is_user else f"「{label}」今天的 AI 总额度"
    percent = (user_part if culprit_is_user else app_part).percent
    return f"{who}已用 {percent}%，写操作、多步任务和办公文档生成暂停，普通查询不受影响。"


def budget_state(*, user_id=None, app_name: str = "smart_assistant", include_usage: bool = False) -> BudgetState:
    """计算当前状态。``include_usage=True`` 时即使没有任何上限也查出用量（给 me 接口展示）。"""
    rows = _snapshot()
    soft = soft_percent(rows)
    if not include_usage and not _has_limits(rows):
        return BudgetState(app_name=app_name, soft_percent=soft)

    user_part = evaluate(user_usage_today(user_id), user_limits(user_id, rows), soft) if user_id else None
    app_part = evaluate(app_usage_today(app_name), app_limits(app_name, rows), soft)
    parts = [p for p in (user_part, app_part) if p is not None]
    state = max((p.state for p in parts), key=_SEVERITY.__getitem__, default=STATE_OK)
    return BudgetState(
        state=state,
        app_name=app_name,
        soft_percent=soft,
        user=user_part,
        app=app_part,
        message=_message(state, user_part, app_part, app_name),
    )


def user_state(user, app_name: str = "smart_assistant") -> BudgetState:
    user_id = getattr(user, "pk", None) if user is not None and getattr(user, "is_authenticated", False) else None
    return budget_state(user_id=user_id, app_name=app_name)


def blocked_message(*, user_id=None, app_name: str) -> str | None:
    state = budget_state(user_id=user_id, app_name=app_name)
    return state.message if state.blocked else None
