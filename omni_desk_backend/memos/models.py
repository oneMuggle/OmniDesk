from django.db import models

from users.models import CustomUser


class Memo(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='memos',
        verbose_name="用户"
    )
    title = models.CharField(max_length=200, verbose_name="标题")
    content = models.TextField(verbose_name="内容", blank=True)
    reminder_time = models.DateTimeField(verbose_name="提醒时间", null=True, blank=True, db_index=True)
    is_completed = models.BooleanField(default=False, verbose_name="是否完成", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        ordering = ['-created_at']
        verbose_name = '备忘录'
        verbose_name_plural = '备忘录管理'

    def __str__(self):
        return self.title
