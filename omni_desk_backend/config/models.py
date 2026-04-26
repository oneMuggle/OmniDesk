from django.contrib.auth.models import Group
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

class OllamaConfig(models.Model):
    alias = models.CharField(_('配置别名'), max_length=100, unique=True)
    api_endpoint = models.URLField(_('API 地址'))
    model = models.CharField(_('模型名称'), max_length=100)
    temperature = models.FloatField(_('Temperature'), default=0.8, null=True, blank=True)
    top_p = models.FloatField(_('Top P'), default=0.9, null=True, blank=True)
    is_default = models.BooleanField(_('是否为默认'), default=False)
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('Ollama 配置')
        verbose_name_plural = _('Ollama 配置')

    def __str__(self):
        return self.alias

    def save(self, *args, **kwargs):
        # 只有当当前实例的 is_default 为 True 时，才更新其他实例
        if self.is_default:
            # 使用 exclude(pk=self.pk) 确保不会将自身设置为 False
            # 并且只更新那些 is_default 已经为 True 的实例
            OllamaConfig.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super(OllamaConfig, self).save(*args, **kwargs)

class Page(models.Model):
    name = models.CharField(_('显示名称'), max_length=255)
    path = models.CharField(_('路由路径'), max_length=255, unique=True)

    class Meta:
        verbose_name = _('页面')
        verbose_name_plural = _('页面')

    def __str__(self):
        return self.name

class PageVisibility(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    is_visible = models.BooleanField(default=True)

    class Meta:
        unique_together = ('page', 'group')
        verbose_name = _('页面可见性')
        verbose_name_plural = _('页面可见性')

    def __str__(self):
        return f"{self.page.name} - {self.group.name}"
