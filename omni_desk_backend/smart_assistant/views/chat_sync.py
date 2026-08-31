"""同步聊天路径编排(create 主体)——从 views/chat.py 拆分。

职责:同步 create 的完整编排(前置上下文 → confirm-replay →
编排执行 → 持久化 → AgentLog → payload),独立成模块以把 chat.py 的
create 路径 C901 复杂度降至 <10。

纯函数依赖复用 ``conversation_manager``(前置上下文/附件/会话/持久化),
本模块不持有 ViewSet 状态;``handle_sync_chat`` 的 ``viewset`` 参数仅为与
Task 4 委托保持兼容而保留,内部不直接使用。

R5-D3:前置段(serializer 校验 → 附件抽取 → 会话加载 → ToolContext 构造 →
附件注入)收敛为 ``prepare_chat_context`` 单次调用;confirm-replay 分支经
``short_circuit`` 回调表达,保持"确认请求在会话加载前短路、绝不 404"的原语义。
"""

import time

from observability import get_logger
from rest_framework import status
from rest_framework.response import Response

from ..agent.orchestrator import AgentOrchestrator, ERROR_KIND_HINTS, classify_error_kind
from ..cache import (
    ConfirmationDraftConsumeError,
    consume_confirmation_draft,
    get_confirmation_draft,
    public_confirmation_draft,
    public_tool_result,
    public_tool_calls_meta,
    safe_public_value,
    sanitize_public_text,
    sanitize_public_sources,
)
from ..hooks.wiring import execute_guarded
from ..models import AgentLog
from ..tools.registry import ToolRegistry
from ..scope import resolve_scope

from .conversation_manager import (
    persist_success,
    prepare_chat_context,
    resolve_error,
    usage_fields,
)

logger = get_logger(__name__, "smart_assistant")


def handle_sync_chat(viewset, request) -> Response:
    """POST /api/smart-assistant/chat/ 同步路径主体(create 编排)。

    ``viewset`` 参数仅用于与 Task 4 委托的调用点保持兼容,本函数内不使用。
    """
    query, tool_context, conversation_history, session, conversation_id, err = prepare_chat_context(
        request,
        require_session=True,
        # confirm-replay 在会话加载前短路(原语义:确认请求绝不因无效
        # conversation_id 返回 404)
        short_circuit=lambda validated: _handle_confirm_replay(request, (validated.get("confirm_token") or "").strip()),
    )
    if err is not None:
        return err[0]

    orchestrator = AgentOrchestrator()

    result, response_time_ms, err_response = _run_sync_process(
        orchestrator,
        query,
        conversation_history,
        tool_context,
        session=session,
        conversation_id=conversation_id,
    )
    if err_response is not None:
        return err_response

    error = resolve_error(result)
    answer = result["answer"]

    # 失败响应不落库：不新建会话、不追加消息，避免错误文本污染多轮上下文
    if not error:
        session, cid = persist_success(session, conversation_id, query, answer, request.user)
        result["conversation_id"] = cid

    # 解析 token 与成本信息
    input_tokens, output_tokens, total_tokens, estimated_cost, model_name = usage_fields(result.get("usage"))

    # 失败时仍写 AgentLog(审计需要),tool_success=False;session 可为空
    log = _write_sync_agent_log(
        session=session,
        query=query,
        answer=answer,
        result=result,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        response_time_ms=response_time_ms,
        error=error,
    )

    return _build_sync_payload(result, log, conversation_id, error)


def _handle_confirm_replay(request, confirm_token) -> Response | None:
    """confirm-replay 子流程:校验 draft / 用户归属 / 工具注册后直接执行工具。

    作为 ``prepare_chat_context`` 的 ``short_circuit`` 回调在会话加载之前调用
    —— 原 sync 语义:前端带 confirm_token 二次请求时跳过 orchestrator 与会话
    加载(orchestrator 已在首次请求时把 draft 存到短期缓存,这里只 replay);
    ``confirm_token`` 为空返回 None,走正常编排路径。
    """
    if not confirm_token:
        return None

    draft_entry = get_confirmation_draft(confirm_token)
    if not draft_entry:
        return Response(
            {"detail": "确认已过期或不存在,请重新发起", "code": "confirmation_expired"},
            status=status.HTTP_410_GONE,
        )
    # 校验 token 归属用户:context_sig 格式 "u<pk>_s<scope>"
    expected_sig = f"u{request.user.pk}_s{resolve_scope(request.user).value}"
    if draft_entry.get("context_sig") != expected_sig:
        # 跨用户重放是安全告警,保留 token 身份以利取证;但只露首尾片段,避免明文全量
        masked = f"{confirm_token[:4]}***{confirm_token[-4:]}" if len(confirm_token) >= 8 else "***"
        logger.warning(
            "confirm token 跨用户重放: token=%s expected_user=%s draft_user_sig=%s",
            masked,
            request.user.pk,
            draft_entry.get("context_sig", ""),
        )
        return Response(
            {"detail": "该确认不属于当前用户", "code": "confirmation_user_mismatch"},
            status=status.HTTP_403_FORBIDDEN,
        )
    # replay 前重新按当前用户执行工具授权，权限撤销后不得执行。
    tool = ToolRegistry.get_tool_for_user(draft_entry["tool_name"], request.user)
    if not tool:
        logger.error("confirm replay 工具未注册: tool_name=%s", draft_entry["tool_name"])
        return Response(
            {"detail": "确认工具不可用，请重新发起", "code": "confirmation_tool_unavailable"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    try:
        claimed = consume_confirmation_draft(confirm_token)
    except ConfirmationDraftConsumeError as exc:
        logger.error(
            "confirm replay token consume unavailable: failure_kind=%s exc_type=%s",
            exc.failure_kind,
            type(exc).__name__,
        )
        return Response(
            {"detail": "确认服务暂不可用，请稍后重试", "code": "confirmation_service_unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as exc:
        logger.error(
            "confirm replay token consume unexpected failure: exc_type=%s",
            type(exc).__name__,
        )
        return Response(
            {"detail": "确认服务暂不可用，请稍后重试", "code": "confirmation_service_unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if claimed is None:
        return Response({"detail": "确认已被使用，请重新发起", "code": "confirmation_already_used"}, status=status.HTTP_409_CONFLICT)
    draft_entry = claimed
    try:
        tool_result = execute_guarded(
            tool,
            draft_entry["user_query"],
            context={
                "history": [],
                "confirmed": True,
                "confirm_token": confirm_token,
                "user": request.user,
                "task_id": draft_entry.get("task_id"),
                "draft": draft_entry.get("draft", {}).get("fields"),
            },
        )
        return Response(
            {
                "answer": tool_result.get("summary") or "操作已完成",
                "tool_used": tool.name,
                "tool_result": public_tool_result(tool_result, tool.name),
                "confirmed": True,
                "error": False,
            }
        )
    except Exception as exc:
        # token 是一次性确认票据,明文写日志有泄露风险;记前缀+长度足以定位
        logger.exception(
            "confirm replay 执行失败: token_prefix=%s len=%d",
            confirm_token[:6],
            len(confirm_token),
        )
        return Response({"detail": "智能助手操作失败，请稍后重试", "code": "confirmation_failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _run_sync_process(
    orchestrator,
    query,
    conversation_history,
    tool_context,
    *,
    session,
    conversation_id,
):
    """执行编排并统一收口异常(P0-K:持久化 last_error 供前端展示/运维排查)。

    返回 ``(result, response_time_ms, err_response)``;编排正常时
    ``err_response`` 为 None,异常时 ``result`` 为 None 且 ``err_response``
    是 500 Response。C-1:conversation_history 保持位置参数(测试用 args[1]
    取参),tool_context 仅以 kwarg 传入(避免与 orchestrator.process 签名冲突)。
    """
    start_time = time.time()
    try:
        result = orchestrator.process(
            query,
            conversation_history,
            tool_context=tool_context,
        )
    except Exception as exc:
        # P0-K:编排层未收口的异常 → 持久化 last_error 供前端展示/运维排查,
        # 不再把 500 裸抛给客户端而不留痕迹。日志仅记长度与异常类型摘要,
        # 避免敏感 query 与完整 traceback 内容进入日志与响应
        logger.warning(
            "智能聊天处理异常: conversation_id=%s query_len=%d exc_type=%s",
            conversation_id,
            len(query) if isinstance(query, str) else 0,
            type(exc).__name__,
        )
        if session is not None:
            session.last_error = type(exc).__name__
            session.save(update_fields=["last_error"])
        return None, 0, Response(
            {"detail": "智能助手处理失败，请稍后重试"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    response_time_ms = int((time.time() - start_time) * 1000)
    return result, response_time_ms, None


def _write_sync_agent_log(
    *,
    session,
    query,
    answer,
    result,
    model_name,
    input_tokens,
    output_tokens,
    total_tokens,
    estimated_cost,
    response_time_ms,
    error,
):
    """create 路径的 AgentLog 审计写入:失败时 tool_success=False,会话可为空。"""
    return AgentLog.objects.create(
        session=session,
        user_query=sanitize_public_text(query),
        intent=result.get("intent") or "unknown",
        tool_used=result.get("tool_used") or "",
        tool_input=safe_public_value({"query": query}),
        tool_output=safe_public_value(result.get("tool_result") or {}),
        llm_response=sanitize_public_text(answer),
        model_name=result.get("model_name") or model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        response_time_ms=response_time_ms,
        tool_success=False if error else (result.get("tool_fallback") is not True),
        # L1 原生 Function Calling 决策日志:透传 orchestrator 的审计字段
        tool_call_path=result.get("tool_call_path") or "json",
        tool_calls_meta=public_tool_calls_meta(result.get("tool_calls_meta") or []),
        tool_calls_rounds=result.get("tool_calls_rounds") or 0,
    )


def _public_sync_tool_result(result):
    """为同步响应生成公开 ToolResult；确认草稿保持安全摘要结构。"""
    if result.get("awaiting_confirmation"):
        tool_result = result.get("tool_result")
        draft = tool_result.get("draft") if isinstance(tool_result, dict) else None
        return {
            "draft": public_confirmation_draft(
                draft,
                result.get("tool_used") or "",
            )
        }
    return public_tool_result(
        result.get("tool_result"),
        result.get("tool_used") or "",
        intent=result.get("intent") or "",
    )


def _build_sync_payload(result, log, conversation_id, error) -> Response:
    """组装同步响应 payload;失败响应在 error=true 基础上追加 kind + hint。"""
    payload = {
        "answer": sanitize_public_text(result.get("answer")),
        "intent": result.get("intent"),
        "tool_used": result.get("tool_used"),
        "tool_result": _public_sync_tool_result(result),
        "sources": sanitize_public_sources(result.get("sources")),
        "conversation_id": result.get("conversation_id") or conversation_id,
        "log_id": log.id,
        "error": error,
        # confirm-replay 框架:若 orchestrator 拦截并返回 awaiting_confirmation,
        # 透传 awaiting_confirmation + confirmation_token 给前端
        "awaiting_confirmation": result.get("awaiting_confirmation", False),
        "confirmation_token": result.get("confirmation_token"),
        # L1 原生 Function Calling 决策日志:透传给前端(A/B 评估 / 审计展示)
        "tool_call_path": result.get("tool_call_path"),
        "tool_calls_meta": public_tool_calls_meta(result.get("tool_calls_meta") or []),
        "tool_calls_rounds": result.get("tool_calls_rounds") or 0,
        # P1A-2:透传 RateLimitHook 拒答字段(写工具速率限制)。
        # 旧字段缺省时为 None,前端按通用错误展示,无 breaking。
        "error_code": result.get("error_code"),
        "retry_after": result.get("retry_after"),
    }
    # 输出契约：失败响应在 error=true 基础上追加机器可读 kind + 中文 hint
    if error:
        kind = classify_error_kind(result)
        payload["kind"] = kind
        payload["hint"] = ERROR_KIND_HINTS.get(kind, ERROR_KIND_HINTS["internal_error"])
    return Response(payload)
