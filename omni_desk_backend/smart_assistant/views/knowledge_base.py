from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from ..models import KnowledgeBaseDocument
from ..serializers import KnowledgeBaseDocumentSerializer
from ..tasks import process_document_embedding


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
        process_document_embedding.delay(doc.id)
