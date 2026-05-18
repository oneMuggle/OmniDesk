from django.db import models
from django.conf import settings


class KnowledgeBaseDocument(models.Model):
    """知识库文档"""
    CATEGORY_CHOICES = [
        ('general', '通用'),
        ('technical', '技术'),
        ('policy', '政策'),
        ('procedure', '流程'),
        ('faq', '常见问题'),
    ]
    title = models.CharField(max_length=255, verbose_name="文档标题")
    file = models.FileField(upload_to='knowledge_base/', verbose_name="文档文件")
    content_text = models.TextField(blank=True, verbose_name="提取的文本内容")
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='general',
        verbose_name="文档分类",
    )
    tags = models.CharField(max_length=500, blank=True, verbose_name="标签（逗号分隔）")
    embedding_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', '待处理'),
            ('processing', '处理中'),
            ('completed', '已完成'),
            ('failed', '失败'),
        ],
        default='pending',
    )
    ragflow_document_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Ragflow 文档ID")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "知识库文档"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class SmartAssistantSession(models.Model):
    """助手会话记录"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assistant_sessions',
    )
    title = models.CharField(max_length=255, verbose_name="会话标题")
    messages = models.JSONField(default=list, verbose_name="对话消息历史")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "助手会话"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


class LlmEndpoint(models.Model):
    """LLM API 端点配置（一次配置，多处复用）"""
    name = models.CharField(max_length=100, verbose_name="配置名称")
    api_endpoint = models.URLField(verbose_name="API 端点")
    api_key = models.CharField(max_length=500, verbose_name="API 密钥")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LLM API 端点"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.api_endpoint})"


class LlmAppConfig(models.Model):
    """LLM 应用配置（为每个应用分配端点+模型+参数）"""
    APP_CHOICES = [
        ('smart_assistant', '智能助手'),
    ]
    app_name = models.CharField(max_length=50, choices=APP_CHOICES, verbose_name="应用名称")
    endpoint = models.ForeignKey(
        LlmEndpoint,
        on_delete=models.CASCADE,
        related_name='app_configs',
        verbose_name="API 端点",
    )
    model_name = models.CharField(max_length=100, verbose_name="模型名称")
    temperature = models.FloatField(null=True, blank=True, default=0.7)
    top_p = models.FloatField(null=True, blank=True, default=0.9)
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LLM 应用配置"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_app_name_display()} - {self.model_name}"


class AgentLog(models.Model):
    """Agent 执行日志（用于调试和审计）"""
    session = models.ForeignKey(
        SmartAssistantSession,
        on_delete=models.CASCADE,
        null=True,
    )
    user_query = models.TextField(verbose_name="用户问题")
    intent = models.CharField(max_length=50, verbose_name="识别的意图类型")
    tool_used = models.CharField(max_length=50, verbose_name="使用的工具")
    tool_input = models.JSONField(default=dict, verbose_name="工具输入")
    tool_output = models.JSONField(default=dict, verbose_name="工具输出")
    llm_response = models.TextField(verbose_name="LLM 回答")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Agent 日志"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
