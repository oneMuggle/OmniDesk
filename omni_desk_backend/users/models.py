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
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    assigned_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_personnel',
        verbose_name='指派人'
    )
    personnel = models.OneToOneField(
        'events.Personnel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_account',
        verbose_name='关联人员'
    )
    
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
    
    
    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
        pass

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        # 管理员拥有所有权限
        if self.is_superuser or self.role == 'admin':
            return True
        
        # 经理的特定权限
        if self.role == 'manager':
            manager_perms = [
                'events.manage_schedule',
                'events.manage_equipment',
                'events.manage_personnel',
                'events.manage_announcements'
            ]
            if perm in manager_perms:
                return True
        
        # 默认情况下，依赖于Django的内置权限系统
        return super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        # 管理员拥有所有模块权限
        if self.is_superuser or self.role == 'admin':
            return True
        # 其他角色暂不使用Django内置权限系统
        return False
