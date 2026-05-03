from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import KnowledgeBaseDocument, SmartAssistantSession, AgentLog
from .serializers import (
    KnowledgeBaseDocumentSerializer,
    SmartAssistantSessionSerializer,
    SmartChatRequestSerializer,
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
                conversation_history = []
            except SmartAssistantSession.DoesNotExist:
                pass

        result = self.orchestrator.process(query, conversation_history)

        AgentLog.objects.create(
            user_query=query,
            intent=result['intent'],
            tool_used=result.get('tool_used') or '',
            tool_input={'query': query},
            tool_output=result.get('tool_result'),
            llm_response=result['answer'],
        )

        return Response({
            'answer': result['answer'],
            'intent': result['intent'],
            'tool_used': result.get('tool_used'),
            'tool_result': result.get('tool_result'),
            'sources': result.get('sources'),
        })


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
