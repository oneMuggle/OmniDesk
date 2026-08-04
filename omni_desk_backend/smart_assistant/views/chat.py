import json
import logging
import time

from django.http import StreamingHttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import SmartAssistantSession, AgentLog
from ..serializers import SmartChatRequestSerializer
from ..agent.orchestrator import (
    AgentOrchestrator,
    ERROR_KIND_HINTS,
    FORMAT_VERSION,
    annotate_error_kind,
    classify_error_kind,
    sse_event,
)
from ..agent.conversation_context import (
    FAILED_ANSWER_STREAM_PREFIX,
    apply_rolling_summary,
    build_effective_history,
    count_turns,
    is_failed_answer,
)
from ..scope import resolve_scope
from ..tools.tool_context import ToolContext
from ..tools.registry import ToolRegistry
from ..cache import get_confirmation_draft, clear_confirmation_draft
from ..hooks.wiring import execute_guarded

logger = logging.getLogger(__name__)


def _resolve_error(result: dict) -> bool:
    """判定编排结果是否为失败响应：优先取显式 error 标记，前缀判断兜底。"""
    return bool(result.get("error")) or is_failed_answer(result.get("answer"))


def _usage_fields(usage):
    """从 usage 字典提取 token 与成本字段（缺失时为 None，不报错）。"""
    usage = usage or {}
    return (
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        usage.get("total_tokens"),
        usage.get("estimated_cost"),
        usage.get("model_name") or "",
    )


class SmartChatViewSet(viewsets.ViewSet):
    """智能聊天接口"""

    permission_classes = [IsAuthenticated]

    def create(self, request):
        """POST /api/smart-assistant/chat/"""
        serializer = SmartChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        query = serializer.validated_data["query"]
        conversation_id = serializer.validated_data.get("conversation_id")
        confirm_token = (serializer.validated_data.get("confirm_token") or "").strip()

        # === confirm-replay:replay 路径(跳过 orchestrator,直接执行工具) ===
        # 前端带 confirm_token 二次请求 → 视图层直接执行工具,不走 orchestrator
        # (orchestrator 已在首次请求时把 draft 存到短期缓存,这里只 replay)
        if confirm_token:
            draft_entry = get_confirmation_draft(confirm_token)
            if not draft_entry:
                return Response(
                    {"detail": "确认已过期或不存在,请重新发起", "code": "confirmation_expired"},
                    status=status.HTTP_410_GONE,
                )
            # 校验 token 归属用户:context_sig 格式 "u<pk>_s<scope>"
            expected_prefix = f"u{request.user.pk}_"
            if not draft_entry.get("context_sig", "").startswith(expected_prefix):
                logger.warning(
                    "confirm token 跨用户重放: token=%s expected_user=%s draft_user_sig=%s",
                    confirm_token,
                    request.user.pk,
                    draft_entry.get("context_sig", ""),
                )
                return Response(
                    {"detail": "该确认不属于当前用户", "code": "confirmation_user_mismatch"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # replay:跳过 orchestrator,直接执行工具
            tool = ToolRegistry.get_tool(draft_entry["tool_name"])
            if not tool:
                logger.error("confirm replay 工具未注册: tool_name=%s", draft_entry["tool_name"])
                return Response(
                    {"detail": f"工具 {draft_entry['tool_name']} 未注册"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            try:
                tool_result = execute_guarded(
                    tool,
                    draft_entry["user_query"],
                    context={"history": [], "confirmed": True, "confirm_token": confirm_token},
                )
                clear_confirmation_draft(confirm_token)  # 清理,防止重放
                return Response({
                    "answer": tool_result.get("summary") or "操作已完成",
                    "tool_used": tool.name,
                    "tool_result": tool_result,
                    "confirmed": True,
                    "error": False,
                })
            except Exception as exc:
                logger.exception("confirm replay 执行失败: token=%s", confirm_token)
                return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # === replay 路径结束 ===

        orchestrator = AgentOrchestrator()

        conversation_history = None
        session = None
        if conversation_id:
            try:
                session = SmartAssistantSession.objects.get(id=conversation_id, user=request.user)
                # 有摘要时用「摘要 + 最近消息」代替全量历史，控制 token 膨胀
                conversation_history = build_effective_history(session.messages, session.summary_text)
            except SmartAssistantSession.DoesNotExist:
                # P0-W:不再静默吞掉无效会话 id —— 避免客户端误以为仍在原上下文中,
                # 实际上却悄悄开了新会话
                logger.warning(
                    "会话不存在或不属于当前用户: conversation_id=%s user_id=%s",
                    conversation_id,
                    request.user.id,
                )
                return Response({"detail": "session not found"}, status=status.HTTP_404_NOT_FOUND)

        start_time = time.time()
        tool_context = ToolContext(user=request.user, scope=resolve_scope(request.user))
        try:
            result = orchestrator.process(query, conversation_history, tool_context=tool_context)
        except Exception as exc:
            # P0-K:编排层未收口的异常 → 持久化 last_error 供前端展示/运维排查,
            # 不再把 500 裸抛给客户端而不留痕迹
            logger.warning("智能聊天处理异常: query=%s conversation_id=%s error=%s", query, conversation_id, exc)
            if session is not None:
                session.last_error = str(exc)
                session.save(update_fields=["last_error"])
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_time_ms = int((time.time() - start_time) * 1000)

        error = _resolve_error(result)
        answer = result["answer"]

        # 失败响应不落库：不新建会话、不追加消息，避免错误文本污染多轮上下文
        if not error:
            if conversation_id and session:
                existing_messages = session.messages or []
                session.messages = existing_messages + [
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": answer},
                ]
                session.turn_count = count_turns(session.messages)
                if not session.title:
                    session.title = query[:50]
                # 滚动摘要：超阈值时压缩早期历史（失败静默降级，不影响主对话）
                apply_rolling_summary(session)
                session.save()
                result["conversation_id"] = session.id
            else:
                session = SmartAssistantSession.objects.create(
                    user=request.user,
                    title=query[:50],
                    messages=[
                        {"role": "user", "content": query},
                        {"role": "assistant", "content": answer},
                    ],
                    turn_count=1,
                )
                result["conversation_id"] = session.id

        # 解析 token 与成本信息
        input_tokens, output_tokens, total_tokens, estimated_cost, model_name = _usage_fields(result.get("usage"))

        # 失败时仍写 AgentLog（审计需要），tool_success=False；session 可为空
        log = AgentLog.objects.create(
            session=session,
            user_query=query,
            intent=result.get("intent") or "unknown",
            tool_used=result.get("tool_used") or "",
            tool_input={"query": query},
            tool_output=result.get("tool_result") or {},
            llm_response=answer,
            model_name=result.get("model_name") or model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            response_time_ms=response_time_ms,
            tool_success=False if error else (result.get("tool_fallback") is not True),
        )

        payload = {
            "answer": answer,
            "intent": result.get("intent"),
            "tool_used": result.get("tool_used"),
            "tool_result": result.get("tool_result"),
            "sources": result.get("sources"),
            "conversation_id": result.get("conversation_id") or conversation_id,
            "log_id": log.id,
            "error": error,
            # confirm-replay 框架:若 orchestrator 拦截并返回 awaiting_confirmation,
            # 透传 awaiting_confirmation + confirmation_token 给前端
            "awaiting_confirmation": result.get("awaiting_confirmation", False),
            "confirmation_token": result.get("confirmation_token"),
        }
        # 输出契约：失败响应在 error=true 基础上追加机器可读 kind + 中文 hint
        if error:
            kind = classify_error_kind(result)
            payload["kind"] = kind
            payload["hint"] = ERROR_KIND_HINTS.get(kind, ERROR_KIND_HINTS["internal_error"])
        return Response(payload)

    @action(detail=False, methods=["post"])
    def stream(self, request):
        """POST /api/smart-assistant/chat/stream/ — SSE 流式响应"""
        serializer = SmartChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        query = serializer.validated_data["query"]
        conversation_id = serializer.validated_data.get("conversation_id")

        conversation_history = None
        session = None
        if conversation_id:
            try:
                session = SmartAssistantSession.objects.get(id=conversation_id, user=request.user)
                conversation_history = build_effective_history(session.messages, session.summary_text)
            except SmartAssistantSession.DoesNotExist:
                pass

        start_time = time.time()

        orchestrator = AgentOrchestrator()
        tool_context = ToolContext(user=request.user, scope=resolve_scope(request.user))

        def event_stream():
            full_answer = []
            meta = {}
            done_error = False
            done_seen = False
            stream_exc = None

            try:
                for chunk in orchestrator.process_stream(query, conversation_history, tool_context=tool_context):
                    yield chunk
                    try:
                        payload = chunk.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
                        data = json.loads(payload)
                    except (IndexError, json.JSONDecodeError):
                        continue
                    event_type = data.get("type")
                    if event_type == "chunk":
                        full_answer.append(data.get("content", ""))
                    elif event_type == "meta":
                        meta = data
                    elif event_type == "done":
                        done_error = bool(data.get("error"))
                        done_seen = True
            except Exception as exc:
                # 生成器中途异常（DB/工具异常逃逸）：按失败路径收口，保证"失败必审计"——
                # 若直接中断流，前端会把已收到的部分内容当成功回答，且 AgentLog 缺失。
                stream_exc = exc
                done_error = True
                logger.exception("SSE 流式生成中途异常: query=%s conversation_id=%s", query, conversation_id)

            partial_answer = "".join(full_answer)
            if stream_exc is not None:
                # 统一采用流式失败前缀，复用 is_failed_answer 语义：
                # 前端失败提示与"失败不落库"逻辑随之自动生效；已累积内容保留进审计记录
                failure_marker = f"{FAILED_ANSWER_STREAM_PREFIX}: 流式生成中断（{stream_exc}）"
                answer = f"{failure_marker}｜已生成部分内容：{partial_answer}" if partial_answer else failure_marker
                # 补发失败 chunk（部分内容此前已 streamed，此处仅补失败标记）
                yield sse_event({"type": "chunk", "content": failure_marker})
                # 生成器未发出 done 时补发携带 kind/hint 的失败 done，让前端完整收尾
                if not done_seen:
                    done_event = {"type": "done", "error": True}
                    annotate_error_kind(
                        done_event,
                        answer,
                        tool_used=meta.get("tool_used"),
                        tool_result=meta.get("tool_result"),
                    )
                    yield sse_event(done_event)
            else:
                answer = partial_answer

            # 失败判定：done 事件显式标记优先，回答前缀兜底
            error = done_error or is_failed_answer(answer)
            response_time_ms = int((time.time() - start_time) * 1000)

            # 失败响应不落库：无 conversation_id 不新建会话，有则不追加消息
            persist_session = session
            cid = conversation_id
            if not error:
                if conversation_id:
                    try:
                        persist_session = SmartAssistantSession.objects.get(id=conversation_id, user=request.user)
                        messages = persist_session.messages or []
                        persist_session.messages = messages + [
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": answer},
                        ]
                        persist_session.turn_count = count_turns(persist_session.messages)
                        if not persist_session.title:
                            persist_session.title = query[:50]
                        apply_rolling_summary(persist_session)
                        persist_session.save()
                        cid = conversation_id
                    except SmartAssistantSession.DoesNotExist:
                        persist_session = None
                        cid = None
                else:
                    persist_session = SmartAssistantSession.objects.create(
                        user=request.user,
                        title=query[:50],
                        messages=[
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": answer},
                        ],
                        turn_count=1,
                    )
                    cid = persist_session.id
            elif not conversation_id:
                persist_session = None
                cid = None

            # 失败时仍写 AgentLog（审计需要），tool_success=False
            log = AgentLog.objects.create(
                session=persist_session,
                user_query=query,
                intent=meta.get("intent") or "unknown",
                tool_used=meta.get("tool_used") or "",
                tool_input={"query": query},
                tool_output=meta.get("tool_result") or {},
                llm_response=answer,
                response_time_ms=response_time_ms,
                # 流式路径暂无 usage 统计，成本留空
                estimated_cost=None,
                tool_success=False if error else (meta.get("tool_fallback") is not True),
            )

            # 输出契约：session 事件携带 format_version；失败时追加 kind + hint
            session_event = {
                "type": "session",
                "format_version": FORMAT_VERSION,
                "conversation_id": cid,
                "log_id": log.id,
                "error": error,
            }
            if error:
                annotate_error_kind(
                    session_event,
                    answer,
                    tool_used=meta.get("tool_used"),
                    tool_result=meta.get("tool_result"),
                )
            yield f"data: {json.dumps(session_event, ensure_ascii=False)}\n\n"

        return StreamingHttpResponse(event_stream(), content_type="text/event-stream")
