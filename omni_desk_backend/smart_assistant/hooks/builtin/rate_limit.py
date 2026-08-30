"""smart_assistant/hooks/builtin/rate_limit.py — 写工具速率限制钩子(P1A-2)。

对 ``require_confirmation=True`` 的工具在 PRE_EXECUTE 阶段返回
``Reject(error_code="rate_limit_exceeded", retry_after=Ns)``,截断同一
用户在固定窗口(默认 60s)内对写工具的反复预演,防止 draft 缓存写风暴
与 audit log 膨胀。

限流算法复用 ``middleware/rate_limit.check_write_rate_limit``(与 chat
限流同源,固定窗口 + Django cache.incr 回落),仅 cache key 命名空间分离。

设计要点:
- read 工具(``require_confirmation=False``)完全不进限流路径,直接放行
- 匿名 / ctx.user 缺失 → 放行,由 ChatMiddleware 兜底匿名拦截
- admin 不豁免(任何人同 1 个用户额度)
- 视 replay 路径(views/chat.py:create())不重跑 hooks,自动避免双计
"""

from __future__ import annotations

from typing import Any

from smart_assistant.middleware.rate_limit import (
    SMART_ASSISTANT_WRITE_RATE_LIMIT,
    check_write_rate_limit,
)

from ..base import Reject, ToolHookBase

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


def _extract_user(ctx: Any) -> Any | None:
    """从 hook ctx 中抽取 user(支持 ToolContext / dict / SimpleNamespace)。

    Returns:
        user 对象;若 ctx 为 None 或不含 user 字段则返回 None。
    """
    if ctx is None:
        return None
    # dict 形态
    if isinstance(ctx, dict):
        return ctx.get("user")
    # dataclass / SimpleNamespace 形态
    return getattr(ctx, "user", None)


class RateLimitHook(ToolHookBase):
    """PRE_EXECUTE:对 require_confirmation=True 工具做 per-user 频次控制。

    注册优先级 25(高于 ConfirmationHook 的 20),保证被限流时不走
    draft / awaiting_confirmation 缓存,避免无效 IO。
    """

    name = "write_rate_limit"

    async def pre_execute(self, tool: Any, ctx: Any, params: dict) -> dict | Reject:
        # read 工具直接放行,不计数
        if not getattr(tool, "require_confirmation", False):
            return params

        if getattr(ctx, "replay", False) or (isinstance(ctx, dict) and ctx.get("replay")):
            return params
        user = _extract_user(ctx)
        if user is None or not getattr(user, "is_authenticated", False):
            return params  # 匿名 / ctx 无 user 由 ChatMiddleware 兜底

        allowed, _remaining, retry_after = check_write_rate_limit(user.id)
        if not allowed:
            logger.warning(
                "写工具限流拦截: user_id=%d, retry_after=%ds",
                getattr(user, "id", -1),
                retry_after,
            )
            return Reject(
                reason=(
                    f"写工具调用过于频繁,请 {retry_after} 秒后再试。"
                    f"当前每用户每分钟上限 {SMART_ASSISTANT_WRITE_RATE_LIMIT} 次"
                ),
                error_code="rate_limit_exceeded",
                retry_after=retry_after,
            )
        return params
