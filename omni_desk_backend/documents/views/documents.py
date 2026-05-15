from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import GeneratedDocument
from .serializers import GeneratedDocumentSerializer


class GeneratedDocumentViewSet(viewsets.ModelViewSet):
    queryset = GeneratedDocument.objects.select_related('generated_by')
    serializer_class = GeneratedDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return self.queryset.filter(generated_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(generated_by=self.request.user)

    @action(detail=True, methods=['post'])
    def finalize(self, request, pk=None):
        document = self.get_object()
        document.is_final = True
        document.save()
        return Response({'status': 'document finalized'})
