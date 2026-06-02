from django.db import models


class ExternalLink(models.Model):
    """第一层集成：内网工具的外链导航"""

    name = models.CharField(max_length=255, verbose_name="名称")
    url = models.URLField(max_length=500, verbose_name="链接地址")
    icon = models.CharField(max_length=50, null=True, blank=True, verbose_name="图标类名")
    description = models.TextField(blank=True, default="", verbose_name="描述")
    category = models.CharField(max_length=100, db_index=True, verbose_name="分类")
    sso_enabled = models.BooleanField(default=False, verbose_name="是否启用 SSO")
    sso_token_endpoint = models.URLField(max_length=500, null=True, blank=True, verbose_name="SSO Token 端点")
    sort_order = models.IntegerField(default=0, verbose_name="排序")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_link"
        ordering = ["category", "sort_order", "name"]
        verbose_name = "外链"
        verbose_name_plural = "外链管理"

    def __str__(self):
        return f"{self.category} - {self.name}"


class IntegrationService(models.Model):
    """第二层集成：带功能调用的内网服务（iframe 嵌入 / API 代理）"""

    INTEGRATION_TYPES = [
        ("iframe", "iframe 嵌入"),
        ("api", "API 代理调用"),
        ("widget", "组件嵌入"),
    ]
    name = models.CharField(max_length=255, unique=True, verbose_name="服务名称")
    slug = models.SlugField(unique=True, verbose_name="标识符")
    description = models.TextField(blank=True, default="", verbose_name="描述")
    integration_type = models.CharField(choices=INTEGRATION_TYPES, max_length=20, verbose_name="集成类型")
    endpoint_url = models.URLField(max_length=500, verbose_name="服务端点")
    api_key = models.CharField(max_length=255, blank=True, default="", verbose_name="API 密钥")
    embed_path = models.CharField(max_length=500, blank=True, default="", verbose_name="嵌入路径/模板")
    config_schema = models.JSONField(default=dict, verbose_name="配置 Schema")
    metadata = models.JSONField(default=dict, verbose_name="元数据")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integration_service"
        ordering = ["name"]
        verbose_name = "集成服务"
        verbose_name_plural = "集成服务管理"

    def __str__(self):
        return f"{self.name} ({self.get_integration_type_display()})"


class Plugin(models.Model):
    """第三层集成：热插拔插件"""

    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("pending_review", "待审核"),
        ("approved", "已批准"),
        ("rejected", "已拒绝"),
        ("disabled", "已禁用"),
    ]
    name = models.CharField(max_length=255, unique=True, verbose_name="插件名称")
    slug = models.SlugField(unique=True, verbose_name="标识符")
    description = models.TextField(blank=True, default="", verbose_name="描述")
    author = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        related_name="plugins",
        verbose_name="作者",
    )
    category = models.CharField(max_length=100, db_index=True, verbose_name="分类")
    icon = models.CharField(max_length=50, null=True, blank=True, verbose_name="图标")
    status = models.CharField(choices=STATUS_CHOICES, default="draft", max_length=20, verbose_name="状态")
    interface_version = models.CharField(max_length=20, default="v1", verbose_name="接口版本")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plugin"
        ordering = ["name"]
        verbose_name = "插件"
        verbose_name_plural = "插件管理"

    def __str__(self):
        return f"{self.name} ({self.status})"


class PluginVersion(models.Model):
    """插件版本"""

    plugin = models.ForeignKey(
        Plugin,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="所属插件",
    )
    version = models.CharField(max_length=20, verbose_name="版本号")
    upload_file = models.FileField(upload_to="plugins/", verbose_name="插件文件")
    file_hash = models.CharField(max_length=64, verbose_name="文件哈希")
    manifest = models.JSONField(default=dict, verbose_name="插件清单")
    is_active = models.BooleanField(default=False, verbose_name="是否激活")
    uploaded_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="上传人",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    review_notes = models.TextField(blank=True, null=True, verbose_name="审核备注")

    class Meta:
        db_table = "plugin_version"
        ordering = ["-uploaded_at"]
        verbose_name = "插件版本"
        verbose_name_plural = "插件版本管理"

    def __str__(self):
        return f"{self.plugin.name} v{self.version}"


class PluginCallLog(models.Model):
    """插件调用审计日志"""

    plugin_version = models.ForeignKey(
        PluginVersion,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="插件版本",
    )
    user = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="调用用户",
    )
    method = models.CharField(max_length=20, verbose_name="调用方法")
    args_summary = models.CharField(max_length=500, blank=True, default="", verbose_name="参数摘要")
    status = models.CharField(max_length=20, verbose_name="执行状态")
    execution_time_ms = models.IntegerField(null=True, verbose_name="执行耗时(ms)")
    error_message = models.TextField(blank=True, null=True, verbose_name="错误信息")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "plugin_call_log"
        ordering = ["-created_at"]
        verbose_name = "插件调用日志"
        verbose_name_plural = "插件调用日志"

    def __str__(self):
        return f"{self.plugin_version} - {self.status} - {self.execution_time_ms}ms"
