from django.db import models

# Create your models here.

class DifyApp(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="应用名称")
    description = models.TextField(blank=True, null=True, verbose_name="应用描述")
    embed_url = models.URLField(max_length=500, verbose_name="嵌入式 URL")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "Dify 应用"
        verbose_name_plural = "Dify 应用"
        ordering = ['name']

    def __str__(self):
        return self.name
