from django.db import models


class Ebook(models.Model):
    """电子书模型"""

    title = models.CharField(max_length=200, verbose_name="书名")
    author = models.CharField(max_length=100, verbose_name="作者", blank=True)
    file = models.FileField(upload_to="ebooks/", verbose_name="文件", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "电子书"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
