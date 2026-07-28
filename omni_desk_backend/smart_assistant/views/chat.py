import json
import time

from django.http import StreamingHttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import SmartAssistantSession, AgentLog
from ..serializers import SmartChatRequestSerializer
from ..agent.orchestrator import AgentOrchestrator
from ..agent.conversation_context import (
    apply_rolling_summary,
    build_effective_history,
    count_turns,
    is_failed_answer,
)
from ..scope import resolve_scope
from ..tools.tool_context import ToolContext


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
        orchestrator = AgentOrchestrator()

        conversation_history = None
        session = None
        if conversation_id:
            try:
                session = SmartAssistantSession.objects.get(id=conversation_id, user=request.user)
                # 有摘要时用「摘要 + 最近消息」代替全量历史，控制 token 膨胀
                conversation_history = build_effective_history(session.messages, session.summary_text)
            except SmartAssistantSession.DoesNotExist:
                pass

        start_time = time.time()
        tool_context = ToolContext(user=request.user, scope=resolve_scope(request.user))
        result = orchestrator.process(query, conversation_history, tool_context=tool_context)
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

        return Response(
            {
                "answer": answer,
                "intent": result.get("intent"),
                "tool_used": result.get("tool_used"),
                "tool_result": result.get("tool_result"),
                "sources": result.get("sources"),
                "conversation_id": result.get("conversation_id") or conversation_id,
                "log_id": log.id,
                "error": error,
            }
        )

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

            answer = "".join(full_answer)
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

            session_event = {
                "type": "session",
                "conversation_id": cid,
                "log_id": log.id,
                "error": error,
            }
            yield f"data: {json.dumps(session_event, ensure_ascii=False)}\n\n"

        return StreamingHttpResponse(event_stream(), content_type="text/event-stream")
