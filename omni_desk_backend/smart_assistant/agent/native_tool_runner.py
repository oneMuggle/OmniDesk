import uuid

from ..hooks.base import Reject
from ..hooks.wiring import (
    apply_failure_hooks,
    apply_post_execute_hooks,
    apply_pre_execute_hooks,
    execute_guarded,
)
from ..cache import public_confirmation_draft, set_confirmation_draft
from .orchestrator_helpers import _dict_to_query, _scope_cache_sig


def execute_native_tool(tool, validated: dict, context) -> tuple[dict, dict | None, dict | None]:
    """原生 tool_calls 路径的单个工具执行(从 AgentOrchestrator._execute_native_tool 提取)。

    行为 100% 不变,保留 C-1/C-2 docstring(修 C-1 + C-2,2026-08-07)。

    对齐 ``_legacy_process`` 的 scope-aware 执行 + 完整 hook 链,替代此前
    直接 ``tool.execute_with_guard(_dict_to_query(validated), context)``:

    - **C-1(越权/跨 scope 泄漏)**:``supports_scope_filter`` 工具经
      ``build_base_queryset`` + ``get_queryset_for_scope`` 派生 scoped
      queryset,再 ``execute_guarded(tool, params, scope, qs, context)``
      执行 —— 确保 SELF/DEPARTMENT/GLOBAL 三级 scope 生效(此前完全跳过
      scope 分支,staff 用户能查到他人数据,已实证 Alice 查 Bob 的 memo)。
    - **C-2(Hook 系统绕过)**:与 legacy 路径一致的 hook 链 ——
      ``require_confirmation`` 工具先经 ``apply_pre_execute_hooks`` 拦截
      (``Reject(confirmation_required)`` → dry_run → 存 draft → 返回
      awaiting_confirmation);执行失败经 ``apply_failure_hooks``;输出统一
      经 ``apply_post_execute_hooks``(PII 脱敏)。此前只走
      ``execute_with_guard``(仅 TimeoutGuardHook),PII 掩码不生效、写工具
      永远拿不到 confirm-replay。

    返回 ``(result, confirmation, failure)``:
        result: 工具输出 dict(post hook 之后;失败时为 failure-hook 结构化兜底)
        confirmation: ``None`` 或 ``{"token": ..., "draft": ...}`` ——
            工具标记需要用户二次确认时返回,调用方应立即终止本轮并透传
            awaiting_confirmation + confirmation_token 给前端。
        failure: ``None`` 或 ``{"error": "execution_failed", "detail": ...}`` ——
            执行抛异常时返回,供调用方写入 tool_calls_meta 审计(与
            F1-era 契约一致,失败工具在审计轨迹中可见)。
    """
    query = _dict_to_query(validated)
    # Fail closed: a destructive tool without confirmation must never execute.
    if getattr(tool, "risk_level", None) == "destructive" and not getattr(
        tool, "require_confirmation", False
    ):
        return (
            {
                "found": False,
                "error": True,
                "error_code": "confirmation_required",
                "message": "破坏性工具必须要求用户确认",
            },
            None,
            {"error": "unsafe_tool_configuration"},
        )
    # I-2:透传完整 validated 字典作为 params,LLM 提供的结构化字段
    # (date_from / chunk_index / department / limit / …)到达工具。
    # query 仍是自然语言主输入(不拼接进 query,保留 F1 防污染决策);
    # 结构化字段经 params 显式传递,工具 opt-in 读取,缺失时回退 query 解析。
    params = validated if isinstance(validated, dict) else {"query": query}
    hook_ctx = context if context is not None else {}

    # C-2:require_confirmation 工具先走 pre-hook 确认拦截(与 legacy 对齐)
    if getattr(tool, "require_confirmation", False):
        hook_result = apply_pre_execute_hooks(tool, hook_ctx, {"query": query})
        if isinstance(hook_result, Reject) and hook_result.error_code == "confirmation_required":
            dry_run_context = {
                "history": [],
                "dry_run": True,
                "user": getattr(context, "user", None),
            }
            dry_run_result = execute_guarded(tool, query, context=dry_run_context)
            draft = dry_run_result.get("draft") if isinstance(dry_run_result, dict) else None
            if not draft:
                return (
                    {
                        "found": False,
                        "message": "该操作暂时无法完成，请稍后重试",
                    },
                    None,
                    None,
                )
            token = str(uuid.uuid4())
            set_confirmation_draft(
                token,
                {
                    "tool_name": tool.name,
                    "user_query": query,
                    "context_sig": _scope_cache_sig(context),
                    "task_id": getattr(context, "task_id", None),
                    "draft": draft,
                },
            )
            return {"found": True, "draft": public_confirmation_draft(draft, tool.name)}, {"token": token, "draft": public_confirmation_draft(draft, tool.name)}, None
        # P1A-2 enforcement:非 confirmation_required 的 Reject(如 rate_limit_exceeded)
        # 直接阻断工具执行,返回 error dict 携带 error_code + retry_after。
        if isinstance(hook_result, Reject) and hook_result.error_code != "confirmation_required":
            return (
                {
                    "found": False,
                    "message": hook_result.reason,
                    "error": True,
                    "error_code": hook_result.error_code,
                    "retry_after": getattr(hook_result, "retry_after", None),
                },
                None,
                {"error": "execution_failed", "detail": hook_result.reason},
            )
        # 非 confirmation_required 的 Reject / 无 pre-hook:走既有执行路径

    failure: dict | None = None
    try:
        # C-1:scope-aware 执行分支(与 _legacy_process 的 414-423 一致)
        if context is not None and getattr(tool, "supports_scope_filter", False):
            base_qs = tool.build_base_queryset()
            scoped_qs = tool.get_queryset_for_scope(base_qs, context)
            result = execute_guarded(
                tool,
                params=params,
                scope=context.scope,
                qs=scoped_qs,
                context=context,
            )
        else:
            result = execute_guarded(tool, query=query, params=params, context=context)
    except Exception as exc:
        # C-2:ON_FAILURE 钩子链(与 legacy 一致):结构化 fallback 优先
        failure = {"error": "execution_failed", "detail": str(exc)}
        recovery = apply_failure_hooks(tool, exc, hook_ctx)
        if recovery.action == "fallback" and isinstance(recovery.fallback_value, dict):
            result = recovery.fallback_value
        else:
            result = {"found": False, "message": f"工具执行失败: {str(exc)}"}
    # C-2:POST_EXECUTE 钩子链(PII 脱敏,统一出口)
    result = apply_post_execute_hooks(tool, result, hook_ctx)
    return result, None, failure
