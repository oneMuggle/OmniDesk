from django.conf import settings
from django.db import models
from django.db.models import JSONField


class DocumentBinding(models.Model):
    """OmniDesk 业务对象 ↔ paperless 文档绑定表"""

    SOURCE_CHOICES = [
        ('project_document', '项目文档'),
        ('contract', '合同'),
        ('policy', '制度文件'),
        ('compliance_report', '合规检查报告'),
        ('personnel_file', '人事档案'),
    ]

    source_type = models.CharField(
        max_length=32, choices=SOURCE_CHOICES, db_index=True, verbose_name='业务源类型'
    )
    source_id = models.PositiveIntegerField(db_index=True, verbose_name='业务源 ID')
    paperless_id = models.PositiveIntegerField(unique=True, verbose_name='paperless 文档 ID')
    paperless_checksum = models.CharField(max_length=64, verbose_name='paperless 校验和')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='paperless_documents',
        verbose_name='所有者',
    )
    title = models.CharField(max_length=255, verbose_name='文档标题')
    correspondent_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='paperless correspondent ID'
    )
    extra_metadata = JSONField(default=dict, blank=True, verbose_name='扩展元数据')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '文档绑定'
        verbose_name_plural = '文档绑定'
        unique_together = [('source_type', 'source_id')]
        indexes = [
            models.Index(fields=['source_type', 'source_id']),
            models.Index(fields=['owner', 'source_type']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_source_type_display()} #{self.source_id} → paperless:{self.paperless_id}'
