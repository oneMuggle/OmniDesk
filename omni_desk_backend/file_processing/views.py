import magic
import csv
import io

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.conf import settings

from .models import UploadedFile, AIAnalysis
from .serializers import UploadedFileSerializer
from .tasks import process_file_task
from .ai.summarizer import DataSummarizer
from .ai.query import NaturalLanguageQuery


# 支持的文件大小限制（10MB）
MAX_FILE_SIZE = getattr(settings, "FILE_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024)

# 支持的 MIME 类型白名单
SUPPORTED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc
    "application/pdf",  # .pdf
}


class FileProcessingViewSet(viewsets.ModelViewSet):
    """文件处理 API"""

    queryset = UploadedFile.objects.all()
    serializer_class = UploadedFileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """只返回当前用户的文件"""
        return UploadedFile.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"])
    def upload(self, request):
        """上传文件"""
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "未提供文件"}, status=status.HTTP_400_BAD_REQUEST)

        # 检查文件大小
        if file.size > MAX_FILE_SIZE:
            max_mb = MAX_FILE_SIZE // (1024 * 1024)
            return Response({"error": f"文件大小超过限制（最大 {max_mb}MB）"}, status=status.HTTP_400_BAD_REQUEST)

        # 使用 python-magic 验证文件真实 MIME 类型（基于文件内容，而非文件名）
        try:
            file_content = file.read(2048)  # 读取前 2KB 用于检测
            file.seek(0)  # 重置文件指针
            real_mime = magic.from_buffer(file_content, mime=True)
        except Exception as e:
            return Response({"error": "无法识别文件类型"}, status=status.HTTP_400_BAD_REQUEST)

        # 特殊处理：xlsx/docx 文件在 magic 中检测为 application/zip
        # 需要结合文件扩展名进行判断
        file_extension = file.name.lower().rsplit(".", 1)[-1] if "." in file.name else ""

        # MIME 类型映射（考虑 magic 检测结果和文件扩展名）
        mime_mapping = {
            ("application/zip", "xlsx"): "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ("application/zip", "docx"): "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ("application/zip", "xls"): "application/vnd.ms-excel",
            ("application/zip", "doc"): "application/msword",
        }

        # 如果检测到 zip 且有匹配的扩展名，使用推断的 MIME 类型
        if (real_mime, file_extension) in mime_mapping:
            real_mime = mime_mapping[(real_mime, file_extension)]

        # 检查 MIME 类型是否在白名单中
        if real_mime not in SUPPORTED_MIME_TYPES:
            return Response({"error": f"不支持的文件类型: {real_mime}"}, status=status.HTTP_400_BAD_REQUEST)

        # 使用检测到的真实 MIME 类型，而非文件名推断
        uploaded_file = UploadedFile.objects.create(
            user=request.user,
            original_filename=file.name,
            file=file,
            file_size=file.size,
            mime_type=real_mime,
        )

        process_file_task.delay(str(uploaded_file.id))

        return Response(
            {
                "id": str(uploaded_file.id),
                "status": uploaded_file.status,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        """获取文件预览数据"""
        uploaded_file = self.get_object()

        if uploaded_file.status != "completed":
            return Response(
                {
                    "status": uploaded_file.status,
                    "error": uploaded_file.error_message,
                }
            )

        result = uploaded_file.result

        return Response(
            {
                "file_id": str(uploaded_file.id),
                "filename": uploaded_file.original_filename,
                "mime_type": uploaded_file.mime_type,
                "sheet_count": uploaded_file.sheet_count,
                "sheets": result.sheets_data,
                "markdown": result.content_markdown,
            }
        )

    @action(detail=True, methods=["post"])
    def analyze(self, request, pk=None):
        """AI 数据分析"""
        uploaded_file = self.get_object()

        if uploaded_file.status != "completed":
            return Response({"error": "文件尚未处理完成"}, status=status.HTTP_400_BAD_REQUEST)

        result = uploaded_file.result
        summarizer = DataSummarizer()
        summary = summarizer.summarize_table(result.sheets_data)

        analysis = AIAnalysis.objects.create(
            file=uploaded_file,
            analysis_type="summary",
            result_text=f"共 {summary['sheet_count']} 个 Sheet，{summary['total_rows']} 行数据",
            result_data=summary,
        )

        return Response(
            {
                "analysis_id": str(analysis.id),
                "summary": summary,
            }
        )

    @action(detail=True, methods=["post"])
    def query(self, request, pk=None):
        """自然语言查询"""
        uploaded_file = self.get_object()

        if uploaded_file.status != "completed":
            return Response({"error": "文件尚未处理完成"}, status=status.HTTP_400_BAD_REQUEST)

        question = request.data.get("question")
        if not question:
            return Response({"error": "未提供问题"}, status=status.HTTP_400_BAD_REQUEST)

        # 限制问题长度，防止资源耗尽和 prompt 注入
        MAX_QUESTION_LENGTH = 2000
        if len(question) > MAX_QUESTION_LENGTH:
            return Response(
                {"error": f"问题长度超过限制（最大 {MAX_QUESTION_LENGTH} 字符）"}, status=status.HTTP_400_BAD_REQUEST
            )

        result = uploaded_file.result
        nl_query = NaturalLanguageQuery()
        answer = nl_query.query(question, {"sheets_data": result.sheets_data})

        analysis = AIAnalysis.objects.create(
            file=uploaded_file,
            analysis_type="query",
            query_text=question,
            result_text=answer,
        )

        return Response(
            {
                "analysis_id": str(analysis.id),
                "question": question,
                "answer": answer,
            }
        )

    @action(detail=True, methods=["get"], url_path=r"export/(?P<file_format>[a-zA-Z]+)")
    def export(self, request, pk=None, file_format=None):
        """导出文件"""
        uploaded_file = self.get_object()

        if uploaded_file.status != "completed":
            return Response({"error": "文件尚未处理完成"}, status=status.HTTP_400_BAD_REQUEST)

        result = uploaded_file.result

        if file_format == "csv":
            # 防止 CSV 公式注入：对以危险字符开头的字段添加前导单引号
            content = result.content_text
            # 简单的公式注入防护：对每行以 =, +, -, @ 开头的内容添加单引号
            sanitized_lines = []
            for line in content.splitlines():
                # 处理 CSV 中的每个字段
                reader = csv.reader(io.StringIO(line))
                try:
                    fields = next(reader)
                    sanitized_fields = []
                    for field in fields:
                        # 如果字段以危险字符开头，添加单引号
                        if field and field[0] in ("=", "+", "-", "@"):
                            sanitized_fields.append("'" + field)
                        else:
                            sanitized_fields.append(field)
                    # 重新组合为 CSV 行
                    output = io.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(sanitized_fields)
                    sanitized_lines.append(output.getvalue().strip())
                except StopIteration:
                    sanitized_lines.append(line)
            sanitized_content = "\n".join(sanitized_lines)
            return HttpResponse(sanitized_content, content_type="text/csv")
        elif file_format == "markdown":
            content = result.content_markdown
            return HttpResponse(content, content_type="text/markdown")
        elif file_format == "excel":
            return Response({"error": "Excel 导出尚未实现"}, status=status.HTTP_501_NOT_IMPLEMENTED)

        return Response({"error": f"不支持的导出格式: {file_format}"}, status=status.HTTP_400_BAD_REQUEST)
