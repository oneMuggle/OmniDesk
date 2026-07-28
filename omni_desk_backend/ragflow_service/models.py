from django.db import models

from personnel.models import EncryptedCharField


class RagflowConfig(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="配置名称")
    api_endpoint = models.URLField(max_length=500, verbose_name="Ragflow API 端点")
    # API 密钥改为加密存储（与 LlmEndpoint.api_key 同一套 EncryptedCharField 方案）。
    # max_length 由 255 放宽到 500：XOR+base64 密文会比明文膨胀约 1/3，
    # 原长度不足以容纳较长密钥的密文。
    api_key = EncryptedCharField(max_length=500, blank=True, null=True, verbose_name="API 密钥")
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
