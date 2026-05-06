from django.db import models
from users.models import CustomUser


class Notification(models.Model):
    TYPE_CHOICES = [
        ('schedule_change', '排班变更'),
        ('announcement', '公告发布'),
        ('memo_due', '备忘录到期'),
        ('calibration_reminder', '校准提醒'),
        ('project_update', '项目更新'),
        ('compliance_issue', '合规问题'),
        ('system', '系统通知'),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='接收用户'
    )
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, verbose_name='通知类型')
    title = models.CharField(max_length=200, verbose_name='标题')
    content = models.TextField(verbose_name='内容')
    link = models.CharField(max_length=500, blank=True, verbose_name='跳转链接')
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    is_system = models.BooleanField(default=False, verbose_name='系统通知')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        ordering = ['-created_at']
        verbose_name = '通知'
        verbose_name_plural = '通知管理'

    def __str__(self):
        return f'[{self.get_type_display()}] {self.title}'
