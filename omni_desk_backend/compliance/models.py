from django.db import models

from documents.models import Book, DocumentTemplate
from projects.models import Project


class ComplianceIssue(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='compliance_issues',
        verbose_name="所属项目"
    )
    document_book = models.ForeignKey(
        Book,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='compliance_issues',
        verbose_name="关联书籍"
    )
    document_template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='compliance_issues',
        verbose_name="关联文档模板"
    )

    ISSUE_TYPES = [
        ('不规范', '不规范'),
        ('时间冲突', '时间冲突'),
        ('内容缺失', '内容缺失'),
        ('内容与规定不符', '内容与规定不符'),
        ('其他', '其他'),
    ]
    issue_type = models.CharField(
        max_length=50,
        choices=ISSUE_TYPES,
        verbose_name="问题类型"
    )
    description = models.TextField(verbose_name="问题描述")
    location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="问题位置"
    ) # 例如：页码、段落、图片区域

    STATUS_CHOICES = [
        ('待处理', '待处理'),
        ('处理中', '处理中'),
        ('已解决', '已解决'),
        ('已忽略', '已忽略'),
    ]
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='待处理',
        verbose_name="处理状态",
        db_index=True,
    )

    SEVERITY_CHOICES = [
        ('低', '低'),
        ('中', '中'),
        ('高', '高'),
        ('紧急', '紧急'),
    ]
    severity = models.CharField(
        max_length=50,
        choices=SEVERITY_CHOICES,
        default='中',
        verbose_name="严重程度"
    )

    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="截止日期",
        db_index=True,
    ) # 针对有时间要求的规范

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "合规问题"
        verbose_name_plural = "合规问题"
        ordering = ['status', '-severity', 'due_date']

    def __str__(self):
        doc_name = ""
        if self.document_book:
            doc_name = self.document_book.title
        elif self.document_template:
            doc_name = self.document_template.name
        return f"[{self.project.name}] {self.issue_type} - {self.description[:50]}... (文档: {doc_name})"
