from django.db import models
from django.utils import timezone

from users.models import CustomUser


class ActiveMemoManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Memo(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="memos", verbose_name="用户")
    title = models.CharField(max_length=200, verbose_name="标题")
    content = models.TextField(verbose_name="内容", blank=True)
    reminder_time = models.DateTimeField(verbose_name="提醒时间", null=True, blank=True, db_index=True)
    is_completed = models.BooleanField(default=False, verbose_name="是否完成", db_index=True)
    is_deleted = models.BooleanField(default=False, verbose_name="是否已删除", db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="删除时间")
    reminder_sent = models.BooleanField(
        default=False,
        verbose_name="到期提醒已发送",
        db_index=True,
        help_text="P0-2:定时任务发送到期提醒后置 True,防止 beat 重复执行时重复提醒",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    objects = ActiveMemoManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "备忘录"
        verbose_name_plural = "备忘录管理"

    def __str__(self):
        return self.title
