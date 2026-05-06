from django.db.models import Q
from django.http import StreamingHttpResponse
from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action

from .models import KnowledgeBaseDocument, SmartAssistantSession, AgentLog
from .serializers import (
    KnowledgeBaseDocumentSerializer,
    SmartAssistantSessionSerializer,
    SmartChatRequestSerializer,
    AgentLogSerializer,
)
from .agent.orchestrator import AgentOrchestrator
from .tasks import process_document_embedding


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

        # 追加对话历史
        if conversation_id:
            session.messages = messages + [
                {'role': 'user', 'content': query},
                {'role': 'assistant', 'content': result['answer']},
            ]
            if not session.title:
                session.title = query[:50]
            session.save()
        else:
            # 自动创建会话
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
            import json
            full_answer = []

            for chunk in self.orchestrator.process_stream(query, conversation_history):
                yield chunk
                # 收集完整回答用于持久化
                try:
                    # SSE 格式: "data: {...}\n\n"
                    payload = chunk.split('data: ', 1)[1].rsplit('\n\n', 1)[0]
                    data = json.loads(payload)
                    if data.get('type') == 'chunk':
                        full_answer.append(data['content'])
                except (IndexError, json.JSONDecodeError):
                    pass

            # 持久化对话
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

            # 追加发送会话 ID
            yield f"data: {json.dumps({'type': 'session', 'conversation_id': cid})}\n\n"

        return StreamingHttpResponse(event_stream(), content_type='text/event-stream')


class SessionViewSet(viewsets.ModelViewSet):
    """会话管理：列表/创建/查看/删除"""
    serializer_class = SmartAssistantSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SmartAssistantSession.objects.filter(
            user=self.request.user
        ).order_by('-updated_at')

    def perform_destroy(self, instance):
        # 仅删除当前用户拥有的会话
        if instance.user == self.request.user:
            instance.delete()


class KnowledgeBaseViewSet(viewsets.ModelViewSet):
    """知识库文档管理"""
    serializer_class = KnowledgeBaseDocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return KnowledgeBaseDocument.objects.filter(
            uploaded_by=self.request.user
        )

    def perform_create(self, serializer):
        doc = serializer.save(uploaded_by=self.request.user)
        # 触发异步向量化任务
        process_document_embedding.delay(doc.id)


class AgentLogViewSet(mixins.ListModelMixin,
                      mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    """Agent 日志审计：列表（支持过滤）+ 详情"""
    serializer_class = AgentLogSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']

    def get_queryset(self):
        qs = AgentLog.objects.all()

        # 按意图过滤
        intent = self.request.query_params.get('intent')
        if intent:
            qs = qs.filter(intent=intent)

        # 按用户过滤（仅管理员）
        user_id = self.request.query_params.get('user_id')
        if user_id and self.request.user.is_staff:
            qs = qs.filter(session__user_id=user_id)

        # 按时间范围过滤
        start = self.request.query_params.get('start_time')
        end = self.request.query_params.get('end_time')
        if start:
            qs = qs.filter(created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lte=end)

        # 关键词搜索
        keyword = self.request.query_params.get('keyword')
        if keyword:
            qs = qs.filter(
                Q(user_query__icontains=keyword) |
                Q(llm_response__icontains=keyword)
            )

        return qs
