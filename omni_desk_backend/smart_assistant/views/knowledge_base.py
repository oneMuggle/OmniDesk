import os
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import FileResponse

from ..models import KnowledgeBaseDocument, KnowledgeDataset
from ..serializers import KnowledgeBaseDocumentSerializer, KnowledgeDatasetSerializer
from ..tasks import process_document_embedding


class KnowledgeBaseViewSet(viewsets.ModelViewSet):
    """知识库文档管理"""

    serializer_class = KnowledgeBaseDocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = KnowledgeBaseDocument.objects.filter(uploaded_by=self.request.user)
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        return qs

    def perform_create(self, serializer):
        doc = serializer.save(uploaded_by=self.request.user)
        process_document_embedding.delay(doc.id)

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        """GET /api/smart-assistant/knowledge-base/documents/{id}/preview/ — 文档预览"""
        doc = self.get_object()
        file_path = doc.file.path
        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".txt", ".md", ".csv"):
            return FileResponse(
                open(file_path, "rb"),
                content_type="text/plain; charset=utf-8",
            )
        elif ext == ".pdf":
            return FileResponse(
                open(file_path, "rb"),
                content_type="application/pdf",
            )
        elif ext in (".docx", ".doc"):
            return Response(
                {
                    "content": doc.content_text or "文档文本尚未提取",
                    "title": doc.title,
                }
            )
        else:
            return Response(
                {"error": f"不支持预览 {ext} 格式"},
                status=400,
            )

    @action(detail=False, methods=["get"])
    def categories(self, request):
        """GET /api/smart-assistant/knowledge-base/documents/categories/ — 获取分类列表"""
        categories = (
            KnowledgeBaseDocument.objects.filter(uploaded_by=request.user).values_list("category", flat=True).distinct()
        )
        return Response(
            {
                "categories": [c for c in categories if c],
            }
        )


class KnowledgeDatasetViewSet(viewsets.ModelViewSet):
    """知识库数据集管理（CRUD）

    数据集为全局共享资源（被 RAGRouter 消费做智能路由），模型无属主字段，
    所有已认证用户均可读写。create/update 的必填校验由
    KnowledgeDatasetSerializer 依据模型字段（name / ragflow_dataset_id 必填）
    自动完成；document_count 为只读统计字段。
    """

    queryset = KnowledgeDataset.objects.all()
    serializer_class = KnowledgeDatasetSerializer
    permission_classes = [IsAuthenticated]
