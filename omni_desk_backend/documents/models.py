from django.db import models
from django.db.models import JSONField
from users.models import CustomUser
from projects.models import Project # Import the Project model

class DocumentTemplate(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='document_templates_in_project',
        verbose_name="所属项目"
    )
    TEMPLATE_TYPES = [
        ('tech_design', '技术方案文档'),
        ('test_case', '测试用例文档'),
        ('meeting_minutes', '会议纪要'),
        ('progress_report', '项目进度报告'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="模板名称")
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES, verbose_name="模板类型")
    content = models.TextField(verbose_name="模板内容")
    extracted_text = models.TextField(blank=True, verbose_name="提取文本") # 新增字段
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

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="标签名")

    class Meta:
        verbose_name = "标签"
        verbose_name_plural = "标签"

    def __str__(self):
        return self.name

class Book(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='books_in_project',
        verbose_name="所属项目"
    )
    title = models.CharField(max_length=200, verbose_name="书名")
    author = models.CharField(max_length=100, blank=True, verbose_name="作者")
    description = models.TextField(blank=True, verbose_name="简介")
    cover_image = models.ImageField(upload_to='covers/', blank=True, null=True, verbose_name="封面图片")
    publication_date = models.DateField(blank=True, null=True, verbose_name="出版日期")
    tags = models.ManyToManyField(Tag, blank=True, related_name='books', verbose_name="标签")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="添加时间")

    class Meta:
        verbose_name = "书籍"
        verbose_name_plural = "书籍"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class Chapter(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='chapters', verbose_name="所属书籍")
    title = models.CharField(max_length=200, verbose_name="章节标题")
    content_md = models.TextField(verbose_name="Markdown内容")
    content_html = models.TextField(verbose_name="HTML内容", blank=True)
    order = models.IntegerField(verbose_name="章节顺序")
    image_metadata = models.JSONField(default=list, blank=True, verbose_name="图片元数据")
    heading_structure = models.JSONField(default=list, blank=True, verbose_name="章节标题结构")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "章节"
        verbose_name_plural = "章节"
        ordering = ['book', 'order']

    def __str__(self):
        return f"{self.book.title} - {self.order}. {self.title}"

class Comment(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='comments', verbose_name="所属章节")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="评论用户")
    content = models.TextField(verbose_name="评论内容")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="评论时间")

    class Meta:
        verbose_name = "评论"
        verbose_name_plural = "评论"
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user} on {self.chapter}"

class Annotation(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='annotations', verbose_name="所属章节")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="批注用户")
    selected_text = models.TextField(verbose_name="选中文本")
    note = models.TextField(verbose_name="批注内容", blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="批注时间")

    class Meta:
        verbose_name = "批注"
        verbose_name_plural = "批注"
        ordering = ['created_at']

    def __str__(self):
        return f"Annotation by {self.user} on {self.chapter}"


class EBook(models.Model):
    title = models.CharField(max_length=200, verbose_name="书名")
    author = models.CharField(max_length=100, blank=True, verbose_name="作者")
    content = models.TextField(verbose_name="Markdown内容")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "电子书"
        verbose_name_plural = "电子书"
        ordering = ['-created_at']

    def __str__(self):
        return self.title
