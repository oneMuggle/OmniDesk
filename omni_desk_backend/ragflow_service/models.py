from django.db import models


class RagflowConfig(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="配置名称")
    api_endpoint = models.URLField(max_length=500, verbose_name="Ragflow API 端点")
    api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="API 密钥")
    chat_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Chat Assistant ID")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "Ragflow 配置"
        verbose_name_plural = "Ragflow 配置"
        ordering = ["name"]

    def __str__(self):
        return self.name
