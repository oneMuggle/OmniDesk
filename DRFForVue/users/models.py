from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', '管理员'),
        ('manager', '经理'), 
        ('user', '普通用户'),
    ]
    
    # 显式定义email字段覆盖默认设置
    email = models.EmailField(blank=True, null=True, help_text='可选字段，允许为空')
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    
    # 使用用户名作为唯一标识
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    # 修复反向访问器冲突
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name="custom_user_groups",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="custom_user_permissions",
        related_query_name="user",
    )
    
    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
        permissions = [
            ('manage_users', '可以管理用户'),
            ('manage_calendar', '可以管理日历'),
            ('manage_documents', '可以管理文档'),
            ('manage_equipment', '可以管理设备'),
            ('manage_settings', '可以管理系统设置'),
            ('manage_schedule', '可以管理日程'),
            ('manage_trials', '可以管理试验'),
            ('manage_personnel', '可以管理人员'),
            ('manage_announcements', '可以管理公告'),
            ('use_ai_chat', '可以使用AI聊天'),
            ('analyze_files', '可以分析文件'),
        ]

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        if self.is_superuser:
            return True
        return super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        if self.is_superuser:
            return True
        return super().has_module_perms(app_label)
