from django.db import models
from django.utils.translation import gettext_lazy as _

class Config(models.Model):
    key = models.CharField(_('配置键'), max_length=100, unique=True)
    value = models.TextField(_('配置值'))
    description = models.TextField(_('描述'), blank=True)
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('系统配置')
        verbose_name_plural = _('系统配置')

    def __str__(self):
        return f"{self.key}: {self.value[:50]}"

class PageConfig(models.Model):
    page_name = models.CharField(_('页面名称'), max_length=100)
    page_path = models.CharField(_('页面路径'), max_length=200, unique=True)
    is_hidden_for_non_admin = models.BooleanField(_('对非管理员隐藏'), default=False)

    class Meta:
        verbose_name = _('页面配置')
        verbose_name_plural = _('页面配置')

    def __str__(self):
        return self.page_name
