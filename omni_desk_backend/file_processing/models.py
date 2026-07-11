import uuid
from django.db import models
from django.conf import settings


class UploadedFile(models.Model):
    """上传文件元数据"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="uploaded_files")
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="uploads/%Y/%m/%d/")
    file_size = models.BigIntegerField(help_text="文件大小（字节）")
    mime_type = models.CharField(max_length=100)

    STATUS_CHOICES = [
        ("pending", "待处理"),
        ("processing", "处理中"),
        ("completed", "已完成"),
        ("failed", "失败"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True)

    sheet_count = models.IntegerField(default=0, help_text="Excel: Sheet 数量")
    page_count = models.IntegerField(default=0, help_text="PDF/Word: 页数")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "上传文件"
        verbose_name_plural = "上传文件"

    def __str__(self):
        return f"{self.original_filename} ({self.status})"


class ProcessingResult(models.Model):
    """文件处理结果"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.OneToOneField(UploadedFile, on_delete=models.CASCADE, related_name="result")

    content_text = models.TextField(blank=True, help_text="纯文本（用于 AI 分析）")
    content_markdown = models.TextField(blank=True, help_text="Markdown 格式")
    content_json = models.JSONField(blank=True, default=dict, help_text="结构化数据")

    sheets_data = models.JSONField(blank=True, default=list, help_text="Excel Sheet 数据")

    row_count = models.IntegerField(default=0)
    column_count = models.IntegerField(default=0)

    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "处理结果"
        verbose_name_plural = "处理结果"

    def __str__(self):
        return f"Result for {self.file.original_filename}"


class AIAnalysis(models.Model):
    """AI 分析结果"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(UploadedFile, on_delete=models.CASCADE, related_name="analyses")

    ANALYSIS_TYPES = [
        ("summary", "数据摘要"),
        ("statistics", "统计分析"),
        ("quality", "数据质量"),
        ("query", "自然语言查询"),
    ]
    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPES)

    query_text = models.TextField(blank=True, help_text="用户查询（仅 query 类型）")
    result_text = models.TextField(help_text="AI 生成的结果")
    result_data = models.JSONField(blank=True, default=dict, help_text="结构化结果")

    model_used = models.CharField(max_length=100, blank=True, help_text="Ollama 模型名")
    tokens_used = models.IntegerField(default=0)
    processing_time_ms = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "AI 分析"
        verbose_name_plural = "AI 分析"

    def __str__(self):
        return f"{self.get_analysis_type_display()} - {self.file.original_filename}"
