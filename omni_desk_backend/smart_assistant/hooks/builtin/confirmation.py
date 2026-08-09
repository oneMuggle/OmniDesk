"""smart_assistant/hooks/builtin/confirmation.py — 写工具二次确认钩子(I-1)。

对 ``require_confirmation=True`` 的工具在 PRE_EXECUTE 阶段返回
``Reject(error_code="confirmation_required")``,激活 orchestrator 现有
confirm-replay 拦截(dry_run → draft → awaiting_confirmation → 前端确认 →
replay 视图执行)。此前无任何 PRE_EXECUTE hook 产生该 Reject,写工具
(office_generate / swap×2)无确认直接执行 —— fail-open 缺口。
"""

from __future__ import annotations

from ..base import Reject, ToolHookBase


class ConfirmationHook(ToolHookBase):
    """PRE_EXECUTE:对 require_confirmation=True 的工具挂起执行,等待用户二次确认。"""

    name = "confirmation"

    async def pre_execute(self, tool, ctx, params):
        if getattr(tool, "require_confirmation", False):
            return Reject(
                reason=f"工具 {getattr(tool, 'name', '')} 需要用户二次确认",
                error_code="confirmation_required",
            )
        return params
