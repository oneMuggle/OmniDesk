"""确认 / 取消写操作的服务函数（S3-1）。

旧的 ``chat`` 接口（带 ``confirm_token``）与新的
``confirmations/{token}/approve|reject/`` 接口共用这里的校验：

1. 草稿不存在或已过期 → 410
2. 草稿不属于当前用户（``context_sig`` 不匹配）→ 403
3. 执行前按当前用户重新授权，工具不可用 → 500（仅确认）
4. 原子消费 token：已被使用 → 409；缓存不可用 → 503

**只有凭 token 调用这里才会执行写操作**；对话中输入"确认"只是一条普通消息。
"""

from __future__ import annotations

from observability import get_logger

from django.core.cache import cache

from ..cache import (
    CONFIRMATION_DRAFT_TTL,
    ConfirmationDraftConsumeError,
    _key,
    consume_confirmation_draft,
    get_confirmation_draft,
)
from ..scope import resolve_scope

logger = get_logger(__name__, "smart_assistant")

#: 工具返回这些 error_code 时，确认接口返回 409
CONFLICT_ERROR_CODES = frozenset({"stale_confirmation", "booking_conflict", "state_conflict"})


class ConfirmationError(Exception):
    """确认 / 取消失败；``status`` 为 HTTP 状态码。"""

    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail

    def as_body(self) -> dict:
        return {"detail": self.detail, "code": self.code}


#: token 被消费后留下的标记：区分"已确认 / 已取消"（409）与"过期 / 不存在"（410）
OUTCOME_APPROVED = "approved"
OUTCOME_REJECTED = "rejected"
_OUTCOME_ERRORS = {
    OUTCOME_APPROVED: ("confirmation_already_used", "该操作已确认执行，请勿重复提交"),
    OUTCOME_REJECTED: ("confirmation_already_rejected", "该操作已取消，请重新发起"),
}


def _outcome_key(token: str) -> str:
    return _key("confirm_outcome", token)


def _mark_outcome(token: str, sig: str, outcome: str) -> None:
    try:
        cache.set(_outcome_key(token), {"sig": sig, "outcome": outcome}, CONFIRMATION_DRAFT_TTL)
    except Exception as exc:  # 标记只影响错误提示的精确度，失败不影响主流程
        logger.warning("confirmation outcome mark failed: exc_type=%s", type(exc).__name__)


def _mask(token: str) -> str:
    return f"{token[:4]}***{token[-4:]}" if len(token) >= 8 else "***"


def _claim(user, token: str, *, need_tool: bool, outcome: str):
    """校验并原子消费草稿；返回 ``(draft_entry, tool)``。"""
    from ..tools.registry import ToolRegistry

    expected_sig = f"u{user.pk}_s{resolve_scope(user).value}"
    draft_entry = get_confirmation_draft(token)
    if not draft_entry:
        marker = cache.get(_outcome_key(token))
        # 只有草稿主人能看到"已确认 / 已取消"；其他人一律视为不存在
        if isinstance(marker, dict) and marker.get("sig") == expected_sig and marker.get("outcome") in _OUTCOME_ERRORS:
            code, detail = _OUTCOME_ERRORS[marker["outcome"]]
            raise ConfirmationError(409, code, detail)
        raise ConfirmationError(410, "confirmation_expired", "确认已过期或不存在,请重新发起")
    if draft_entry.get("context_sig") != expected_sig:
        # 跨用户重放是安全告警,保留 token 身份以利取证;但只露首尾片段,避免明文全量
        logger.warning(
            "confirm token 跨用户重放: token=%s expected_user=%s draft_user_sig=%s",
            _mask(token),
            user.pk,
            draft_entry.get("context_sig", ""),
        )
        raise ConfirmationError(403, "confirmation_user_mismatch", "该确认不属于当前用户")
    tool = None
    if need_tool:
        # replay 前重新按当前用户执行工具授权，权限撤销后不得执行。
        tool = ToolRegistry.get_tool_for_user(draft_entry["tool_name"], user)
        if not tool:
            logger.error("confirm replay 工具未注册: tool_name=%s", draft_entry["tool_name"])
            raise ConfirmationError(500, "confirmation_tool_unavailable", "确认工具不可用，请重新发起")
    try:
        claimed = consume_confirmation_draft(token)
    except ConfirmationDraftConsumeError as exc:
        logger.error(
            "confirm replay token consume unavailable: failure_kind=%s exc_type=%s",
            exc.failure_kind,
            type(exc).__name__,
        )
        raise ConfirmationError(503, "confirmation_service_unavailable", "确认服务暂不可用，请稍后重试") from exc
    except Exception as exc:
        logger.error("confirm replay token consume unexpected failure: exc_type=%s", type(exc).__name__)
        raise ConfirmationError(503, "confirmation_service_unavailable", "确认服务暂不可用，请稍后重试") from exc
    if claimed is None:
        raise ConfirmationError(409, "confirmation_already_used", "确认已被使用，请重新发起")
    _mark_outcome(token, expected_sig, outcome)
    return claimed, tool


def execute_confirmed(user, token: str):
    """消费 token 并执行写工具；返回 ``(tool, tool_result, draft_entry)``。"""
    from ..hooks.wiring import execute_guarded

    draft_entry, tool = _claim(user, token, need_tool=True, outcome=OUTCOME_APPROVED)
    try:
        tool_result = execute_guarded(
            tool,
            draft_entry["user_query"],
            context={
                "history": [],
                "confirmed": True,
                "confirm_token": token,
                "user": user,
                "task_id": draft_entry.get("task_id"),
                "draft": draft_entry.get("draft", {}).get("fields"),
            },
        )
    except Exception as exc:
        # token 是一次性确认票据,明文写日志有泄露风险;记前缀+长度足以定位
        logger.exception("confirm replay 执行失败: token_prefix=%s len=%d", token[:6], len(token))
        raise ConfirmationError(500, "confirmation_failed", "智能助手操作失败，请稍后重试") from exc
    return tool, tool_result, draft_entry


def reject(user, token: str) -> dict:
    """取消：消费 token 使其不能再被确认，并记录一条结构化日志。"""
    draft_entry, _ = _claim(user, token, need_tool=False, outcome=OUTCOME_REJECTED)
    logger.info(
        "confirmation.rejected",
        extra={
            "event": "confirmation.rejected",
            "tool_name": draft_entry.get("tool_name"),
            "user_id": user.pk,
            "task_id": draft_entry.get("task_id"),
        },
    )
    return {"rejected": True, "tool_used": draft_entry.get("tool_name")}


def result_write_meta(tool_result) -> dict:
    """从工具结果中取出写日志 ID 与是否可撤销（供前端显示「撤销」按钮）。"""
    if not isinstance(tool_result, dict):
        return {"write_log_id": None, "reversible": False}
    inner = tool_result.get("result") if isinstance(tool_result.get("result"), dict) else {}
    log_id = tool_result.get("write_log_id", inner.get("write_log_id"))
    reversible = tool_result.get("reversible", inner.get("reversible", False))
    return {"write_log_id": log_id if isinstance(log_id, int) else None, "reversible": bool(reversible and log_id)}
