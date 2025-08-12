from django.db import models
from django.conf import settings

class Project(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="项目名称")
    description = models.TextField(blank=True, verbose_name="项目描述")
    start_date = models.DateField(null=True, blank=True, verbose_name="开始日期")
    end_date = models.DateField(null=True, blank=True, verbose_name="结束日期")
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='managed_projects', 
        verbose_name="项目负责人"
    )
    status = models.CharField(
        max_length=50, 
        default='进行中', 
        choices=[
            ('进行中', '进行中'),
            ('已完成', '已完成'),
            ('已暂停', '已暂停'),
            ('已取消', '已取消'),
        ],
        verbose_name="项目状态"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "项目"
        verbose_name_plural = "项目"
        ordering = ['-created_at']

    def __str__(self):
        return self.name