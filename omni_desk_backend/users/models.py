from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    # 显式定义email字段覆盖默认设置
    email = models.EmailField(blank=True, null=True, help_text="可选字段，允许为空")
    real_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="真实姓名")
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    assigned_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_personnel",
        verbose_name="指派人",
    )
    personnel = models.OneToOneField(
        "personnel.Personnel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_account",
        verbose_name="关联人员",
    )

    # 使用用户名作为唯一标识
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []

    # 修复反向访问器冲突
    groups = models.ManyToManyField(
        "auth.Group",
        verbose_name="groups",
        blank=True,
        help_text="The groups this user belongs to.",
        related_name="custom_user_groups",
        related_query_name="user",
    )

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"
        pass

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        # 默认情况下，依赖于Django的内置权限系统
        return super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        # 默认情况下，依赖于Django的内置权限系统
        return super().has_module_perms(app_label)


class PhoneNumber(models.Model):
    user = models.ForeignKey(CustomUser, related_name="phone_numbers", on_delete=models.CASCADE)
    number = models.CharField(max_length=20, verbose_name="手机号码")

    def __str__(self):
        return self.number


class AuditLogEntry(models.Model):
    """用户-人员关联审计日志(配套 link_user_personnel 管理命令)

    P1-5 引入。每一行记录一次 user.personnel 字段的变更(绑定/解绑),
    包含 batch_id 用于按批次回滚。
    """

    ACTION_LINK = "link"
    ACTION_UNLINK = "unlink"
    ACTION_LINK_SKIPPED = "link_skipped"
    ACTION_UNLINK_SKIPPED = "unlink_skipped"
    ACTION_CHOICES = [
        (ACTION_LINK, "绑定"),
        (ACTION_UNLINK, "解绑"),
        (ACTION_LINK_SKIPPED, "绑定跳过"),
        (ACTION_UNLINK_SKIPPED, "解绑跳过"),
    ]

    batch_id = models.CharField(max_length=64, db_index=True, verbose_name="批次ID")
    actor = models.CharField(max_length=100, blank=True, verbose_name="操作者")
    action = models.CharField(max_length=32, choices=ACTION_CHOICES, verbose_name="动作")
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="audit_log_entries",
        verbose_name="目标用户",
    )
    old_personnel_id = models.IntegerField(null=True, blank=True, verbose_name="原 personnel.id")
    new_personnel_id = models.IntegerField(null=True, blank=True, verbose_name="新 personnel.id")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="元数据")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "用户-人员关联审计日志"
        verbose_name_plural = "用户-人员关联审计日志"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["batch_id", "action"]),
        ]

    def __str__(self):
        return f"[{self.batch_id}] {self.action} user_id={self.target_user_id}"
