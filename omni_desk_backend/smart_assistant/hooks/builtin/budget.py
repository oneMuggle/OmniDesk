"""smart_assistant/hooks/builtin/budget.py — 预算只读钩子(方案 5.6)。

今日用量到软上限(默认 80%)后进入只读:写工具(``require_confirmation=True``)
在 PRE_EXECUTE 返回 ``Reject(error_code="budget_readonly")``,三条执行路径
(原生调用 / JSON / 流式)对非确认类 Reject 已统一阻断并带出提示。

- 状态由对话入口在本轮开始时算好放进 ``ToolContext.budget_readonly``
  (钩子跑在 ``asyncio.run`` 的事件循环里,不能查 ORM);
- 读工具不受影响;
- replay(确认卡回放)不跑钩子,已生成的确认卡仍可确认;
- 注册优先级 30,先于限流(25)与确认(20),被拦时不产生草稿。
"""

from __future__ import annotations

from typing import Any

from observability import get_logger

from ..base import Reject, ToolHookBase

logger = get_logger(__name__, "smart_assistant")

DEFAULT_MESSAGE = "今天的 AI 额度已接近上限,写操作暂停,普通查询不受影响。"


def _ctx_get(ctx: Any, name: str, default=None):
    if ctx is None:
        return default
    if isinstance(ctx, dict):
        return ctx.get(name, default)
    return getattr(ctx, name, default)


class BudgetHook(ToolHookBase):
    """PRE_EXECUTE:预算只读时拒绝写工具。"""

    name = "budget_readonly"

    async def pre_execute(self, tool: Any, ctx: Any, params: dict) -> dict | Reject:
        if not getattr(tool, "require_confirmation", False):
            return params
        if _ctx_get(ctx, "replay", False):
            return params
        if not _ctx_get(ctx, "budget_readonly", False):
            return params
        user = _ctx_get(ctx, "user")
        logger.info(
            "预算只读拦截写工具: user_id=%s tool=%s",
            getattr(user, "id", None),
            getattr(tool, "name", "?"),
        )
        return Reject(
            reason=_ctx_get(ctx, "budget_message", "") or DEFAULT_MESSAGE,
            error_code="budget_readonly",
        )
