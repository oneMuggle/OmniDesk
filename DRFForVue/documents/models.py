from django.db import models
from django.db.models import JSONField
from users.models import CustomUser

class DocumentTemplate(models.Model):
    TEMPLATE_TYPES = [
        ('tech_design', '技术方案文档'),
        ('test_case', '测试用例文档'),
        ('meeting_minutes', '会议纪要'),
        ('progress_report', '项目进度报告'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="模板名称")
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES, verbose_name="模板类型")
    content = models.TextField(verbose_name="模板内容")
    variables = JSONField(default=dict, verbose_name="模板变量")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="所属用户", related_name='document_templates')

    class Meta:
        verbose_name = "文档模板"
        verbose_name_plural = "文档模板"
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.get_template_type_display()} - {self.name}"

class GeneratedDocument(models.Model):
    template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, verbose_name="关联模板")
    content = models.TextField(verbose_name="生成内容")
    variables_used = JSONField(default=dict, verbose_name="使用变量")
    generated_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="生成用户")
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name="生成时间")
    is_final = models.BooleanField(default=False, verbose_name="最终版本")

    class Meta:
        verbose_name = "生成文档"
        verbose_name_plural = "生成文档"
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.template.name} - {self.generated_at.strftime('%Y-%m-%d %H:%M')}"
