import mimetypes

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse

from .models import UploadedFile, AIAnalysis
from .serializers import UploadedFileSerializer
from .tasks import process_file_task
from .ai.summarizer import DataSummarizer
from .ai.query import NaturalLanguageQuery


class FileProcessingViewSet(viewsets.ModelViewSet):
    """文件处理 API"""

    queryset = UploadedFile.objects.all()
    serializer_class = UploadedFileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """只返回当前用户的文件"""
        return UploadedFile.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def upload(self, request):
        """上传文件"""
        file = request.FILES.get('file')
        if not file:
            return Response({'error': '未提供文件'}, status=status.HTTP_400_BAD_REQUEST)

        mime_type, _ = mimetypes.guess_type(file.name)
        if not mime_type:
            mime_type = 'application/octet-stream'

        uploaded_file = UploadedFile.objects.create(
            user=request.user,
            original_filename=file.name,
            file=file,
            file_size=file.size,
            mime_type=mime_type,
        )

        process_file_task.delay(str(uploaded_file.id))

        return Response({
            'id': str(uploaded_file.id),
            'status': uploaded_file.status,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """获取文件预览数据"""
        uploaded_file = self.get_object()

        if uploaded_file.status != 'completed':
            return Response({
                'status': uploaded_file.status,
                'error': uploaded_file.error_message,
            })

        result = uploaded_file.result

        return Response({
            'file_id': str(uploaded_file.id),
            'filename': uploaded_file.original_filename,
            'mime_type': uploaded_file.mime_type,
            'sheet_count': uploaded_file.sheet_count,
            'sheets': result.sheets_data,
            'markdown': result.content_markdown,
        })

    @action(detail=True, methods=['post'])
    def analyze(self, request, pk=None):
        """AI 数据分析"""
        uploaded_file = self.get_object()

        if uploaded_file.status != 'completed':
            return Response({'error': '文件尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST)

        result = uploaded_file.result
        summarizer = DataSummarizer()
        summary = summarizer.summarize_table(result.sheets_data)

        analysis = AIAnalysis.objects.create(
            file=uploaded_file,
            analysis_type='summary',
            result_text=f"共 {summary['sheet_count']} 个 Sheet，{summary['total_rows']} 行数据",
            result_data=summary,
        )

        return Response({
            'analysis_id': str(analysis.id),
            'summary': summary,
        })

    @action(detail=True, methods=['post'])
    def query(self, request, pk=None):
        """自然语言查询"""
        uploaded_file = self.get_object()

        if uploaded_file.status != 'completed':
            return Response({'error': '文件尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST)

        question = request.data.get('question')
        if not question:
            return Response({'error': '未提供问题'}, status=status.HTTP_400_BAD_REQUEST)

        result = uploaded_file.result
        nl_query = NaturalLanguageQuery()
        answer = nl_query.query(question, {'sheets_data': result.sheets_data})

        analysis = AIAnalysis.objects.create(
            file=uploaded_file,
            analysis_type='query',
            query_text=question,
            result_text=answer,
        )

        return Response({
            'analysis_id': str(analysis.id),
            'question': question,
            'answer': answer,
        })

    @action(detail=True, methods=['get'], url_path=r'export/(?P<file_format>[a-zA-Z]+)')
    def export(self, request, pk=None, file_format=None):
        """导出文件"""
        uploaded_file = self.get_object()

        if uploaded_file.status != 'completed':
            return Response({'error': '文件尚未处理完成'}, status=status.HTTP_400_BAD_REQUEST)

        result = uploaded_file.result

        if file_format == 'csv':
            content = result.content_text
            return HttpResponse(content, content_type='text/csv')
        elif file_format == 'markdown':
            content = result.content_markdown
            return HttpResponse(content, content_type='text/markdown')
        elif file_format == 'excel':
            return Response({'error': 'Excel 导出尚未实现'}, status=status.HTTP_501_NOT_IMPLEMENTED)

        return Response({'error': f'不支持的导出格式: {file_format}'}, status=status.HTTP_400_BAD_REQUEST)
