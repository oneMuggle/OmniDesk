from rest_framework import viewsets, permissions, parsers
from .models import DocumentTemplate, GeneratedDocument
from .serializers import DocumentTemplateSerializer, GeneratedDocumentSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

class DocumentTemplateViewSet(viewsets.ModelViewSet):
    queryset = DocumentTemplate.objects.all()
    serializer_class = DocumentTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser]  # 添加文件上传支持

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=False, methods=['post'], url_path='upload')
    def upload_template(self, request):
        file_obj = request.FILES.get('template')
        if not file_obj:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            template = DocumentTemplate.objects.create(
                name=file_obj.name,
                file=file_obj,
                owner=request.user
            )
            return Response(DocumentTemplateSerializer(template).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='analyze')
    def analyze_file(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # TODO: 实现实际的文件解析逻辑
            # 这里模拟解析结果
            result = {
                'fileName': file_obj.name,
                'people': [
                    {'name': '张三', 'origin': '北京', 'age': 30},
                    {'name': '李四', 'origin': '上海', 'age': 25}
                ]
            }
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GeneratedDocumentViewSet(viewsets.ModelViewSet):
    queryset = GeneratedDocument.objects.all()
    serializer_class = GeneratedDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # 禁用分页

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
