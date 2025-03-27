from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    # 显式定义email字段覆盖默认设置
    email = models.EmailField(blank=True, null=True, help_text='可选字段，允许为空')
    phone = models.CharField(max_length=20, blank=True, null=True)
    
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

    def __str__(self):
        return self.username
