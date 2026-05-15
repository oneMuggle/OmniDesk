import json

from django.http import StreamingHttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import SmartAssistantSession, AgentLog
from ..serializers import SmartChatRequestSerializer
from ..agent.orchestrator import AgentOrchestrator


class SmartChatViewSet(viewsets.ViewSet):
    """智能聊天接口"""
    permission_classes = [IsAuthenticated]
    orchestrator = AgentOrchestrator()

    def create(self, request):
        """POST /api/smart-assistant/chat/"""
        serializer = SmartChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        query = serializer.validated_data['query']
        conversation_id = serializer.validated_data.get('conversation_id')

        conversation_history = None
        if conversation_id:
            try:
                session = SmartAssistantSession.objects.get(
                    id=conversation_id, user=request.user
                )
                messages = session.messages or []
                conversation_history = messages
            except SmartAssistantSession.DoesNotExist:
                pass

        result = self.orchestrator.process(query, conversation_history)

        if conversation_id:
            session.messages = messages + [
                {'role': 'user', 'content': query},
                {'role': 'assistant', 'content': result['answer']},
            ]
            if not session.title:
                session.title = query[:50]
            session.save()
        else:
            session = SmartAssistantSession.objects.create(
                user=request.user,
                title=query[:50],
                messages=[
                    {'role': 'user', 'content': query},
                    {'role': 'assistant', 'content': result['answer']},
                ],
            )
            result['conversation_id'] = session.id

        AgentLog.objects.create(
            session_id=conversation_id,
            user_query=query,
            intent=result['intent'],
            tool_used=result.get('tool_used') or '',
            tool_input={'query': query},
            tool_output=result.get('tool_result') or {},
            llm_response=result['answer'],
        )

        return Response({
            'answer': result['answer'],
            'intent': result['intent'],
            'tool_used': result.get('tool_used'),
            'tool_result': result.get('tool_result'),
            'sources': result.get('sources'),
            'conversation_id': result.get('conversation_id') or conversation_id,
        })

    @action(detail=False, methods=['post'])
    def stream(self, request):
        """POST /api/smart-assistant/chat/stream/ — SSE 流式响应"""
        serializer = SmartChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        query = serializer.validated_data['query']
        conversation_id = serializer.validated_data.get('conversation_id')

        conversation_history = None
        if conversation_id:
            try:
                session = SmartAssistantSession.objects.get(
                    id=conversation_id, user=request.user
                )
                conversation_history = session.messages or []
            except SmartAssistantSession.DoesNotExist:
                pass

        def event_stream():
            full_answer = []

            for chunk in self.orchestrator.process_stream(query, conversation_history):
                yield chunk
                try:
                    payload = chunk.split('data: ', 1)[1].rsplit('\n\n', 1)[0]
                    data = json.loads(payload)
                    if data.get('type') == 'chunk':
                        full_answer.append(data['content'])
                except (IndexError, json.JSONDecodeError):
                    pass

            answer = ''.join(full_answer)
            if conversation_id:
                try:
                    session = SmartAssistantSession.objects.get(
                        id=conversation_id, user=request.user
                    )
                    messages = session.messages or []
                    session.messages = messages + [
                        {'role': 'user', 'content': query},
                        {'role': 'assistant', 'content': answer},
                    ]
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
                        {'role': 'user', 'content': query},
                        {'role': 'assistant', 'content': answer},
                    ],
                )
                cid = session.id

            yield f"data: {json.dumps({'type': 'session', 'conversation_id': cid})}\n\n"

        return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
