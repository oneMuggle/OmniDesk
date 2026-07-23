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
from ..agent.conversation_context import count_turns
from ..scope import resolve_scope
from ..tools.tool_context import ToolContext


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
                conversation_history = session.messages or []
            except SmartAssistantSession.DoesNotExist:
                pass

        start_time = time.time()
        tool_context = ToolContext(user=request.user, scope=resolve_scope(request.user))
        result = orchestrator.process(query, conversation_history, tool_context=tool_context)
        response_time_ms = int((time.time() - start_time) * 1000)

        if conversation_id and session:
            existing_messages = session.messages or []
            session.messages = existing_messages + [
                {"role": "user", "content": query},
                {"role": "assistant", "content": result["answer"]},
            ]
            session.turn_count = count_turns(session.messages)
            if not session.title:
                session.title = query[:50]
            session.save()
            result["conversation_id"] = session.id
        else:
            session = SmartAssistantSession.objects.create(
                user=request.user,
                title=query[:50],
                messages=[
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": result["answer"]},
                ],
                turn_count=1,
            )
            result["conversation_id"] = session.id

        # 解析 token 信息
        usage = result.get("usage")
        input_tokens = None
        output_tokens = None
        total_tokens = None
        if usage:
            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")

        AgentLog.objects.create(
            session=session,
            user_query=query,
            intent=result["intent"],
            tool_used=result.get("tool_used") or "",
            tool_input={"query": query},
            tool_output=result.get("tool_result") or {},
            llm_response=result["answer"],
            model_name=result.get("model_name", ""),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            response_time_ms=response_time_ms,
            tool_success=result.get("tool_fallback") is not True,
        )

        return Response(
            {
                "answer": result["answer"],
                "intent": result["intent"],
                "tool_used": result.get("tool_used"),
                "tool_result": result.get("tool_result"),
                "sources": result.get("sources"),
                "conversation_id": result.get("conversation_id") or conversation_id,
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
                conversation_history = session.messages or []
            except SmartAssistantSession.DoesNotExist:
                pass

        start_time = time.time()

        orchestrator = AgentOrchestrator()
        tool_context = ToolContext(user=request.user, scope=resolve_scope(request.user))

        def event_stream():
            full_answer = []

            for chunk in orchestrator.process_stream(query, conversation_history, tool_context=tool_context):
                yield chunk
                try:
                    payload = chunk.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
                    data = json.loads(payload)
                    if data.get("type") == "chunk":
                        full_answer.append(data["content"])
                except (IndexError, json.JSONDecodeError):
                    pass

            answer = "".join(full_answer)
            response_time_ms = int((time.time() - start_time) * 1000)

            if conversation_id:
                try:
                    session = SmartAssistantSession.objects.get(id=conversation_id, user=request.user)
                    messages = session.messages or []
                    session.messages = messages + [
                        {"role": "user", "content": query},
                        {"role": "assistant", "content": answer},
                    ]
                    session.turn_count = count_turns(session.messages)
                    if not session.title:
                        session.title = query[:50]
                    session.save()
                    cid = conversation_id
                except SmartAssistantSession.DoesNotExist:
                    cid = None
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
                cid = session.id

            yield f"data: {json.dumps({'type': 'session', 'conversation_id': cid})}\n\n"

        return StreamingHttpResponse(event_stream(), content_type="text/event-stream")
