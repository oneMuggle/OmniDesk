"""对话 / 任务入口复用的预算辅助函数。"""

from __future__ import annotations

from dataclasses import replace

from observability import get_logger

from .policy import BudgetState, user_state

logger = get_logger(__name__, "smart_assistant")

BUDGET_EXCEEDED = "budget_exceeded"
BUDGET_READONLY = "budget_readonly"


def safe_user_state(user, app_name: str = "smart_assistant") -> BudgetState:
    """计算状态;出错时放行(ok),只写日志。"""
    try:
        return user_state(user, app_name)
    except Exception as exc:
        logger.warning("预算状态计算失败，放行: app=%s type=%s", app_name, type(exc).__name__)
        return BudgetState(app_name=app_name)


def apply_budget(tool_context):
    """本轮开始时计算状态;只读时在 ToolContext 上关掉写工具与任务计划卡。

    返回 ``(tool_context, state)``。
    """
    state = safe_user_state(getattr(tool_context, "user", None))
    if state.readonly and tool_context is not None:
        tool_context = replace(
            tool_context,
            budget_readonly=True,
            budget_message=state.message,
            task_proposal_allowed=False,
        )
    return tool_context, state


def blocked_result(message: str) -> dict:
    """硬上限时代替编排结果的失败回答。"""
    return {
        "answer": message,
        "error": True,
        "error_code": BUDGET_EXCEEDED,
        "intent": BUDGET_EXCEEDED,
        "tool_used": None,
        "tool_result": None,
        "sources": [],
    }


def apply_midturn_block(result: dict, scope) -> dict:
    """本轮中途被路由兜底拦下且最终失败时,把通用失败改写为「额度已用完」。"""
    message = getattr(scope, "blocked_message", "") if scope is not None else ""
    if message and result.get("error"):
        result = {**result, "answer": message, "error_code": BUDGET_EXCEEDED}
    return result


def public_budget(state: BudgetState | None) -> dict | None:
    """响应里带给前端的简要状态;ok 时为 None。"""
    if state is None or state.state == "ok":
        return None
    return {"state": state.state, "message": state.message}


def usage_from_scope(scope, fallback_usage) -> dict | None:
    """AgentLog 回填:本轮有计量到调用时用合计,否则保留编排结果里的 usage。"""
    if scope is None or not scope.calls:
        return fallback_usage
    usage = dict(fallback_usage or {})
    usage.update(
        {
            "prompt_tokens": scope.prompt_tokens,
            "completion_tokens": scope.completion_tokens,
            "total_tokens": scope.total_tokens,
            "estimated_cost": scope.estimated_cost,
        }
    )
    return usage


def budget_gate(user, app_name: str, *, block_readonly: bool):
    """非对话入口(办公助手 / 文件处理 / 合规报告抽取)的前置检查。

    硬上限一律拒绝;``block_readonly=True`` 时只读也拒绝(办公文档生成属于只读暂停范围)。
    需要拒绝时返回 429 ``Response``,否则 None。
    """
    state = safe_user_state(user, app_name)
    if state.blocked or (block_readonly and state.readonly):
        return budget_response(state.message, BUDGET_EXCEEDED if state.blocked else BUDGET_READONLY, state)
    return None


def budget_response(message: str, code: str = BUDGET_EXCEEDED, state: BudgetState | None = None):
    from rest_framework import status
    from rest_framework.response import Response

    return Response(
        {"error": message, "detail": message, "error_code": code, "budget": public_budget(state)},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )
