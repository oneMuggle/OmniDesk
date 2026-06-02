from django.contrib.auth.models import Group
from django.db import models

# Create your models here.


class PageRoute(models.Model):
    name = models.CharField(max_length=100, verbose_name="页面名称")
    path = models.CharField(max_length=255, unique=True, verbose_name="路由路径")
    component = models.CharField(max_length=255, verbose_name="前端组件")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children", verbose_name="父级页面"
    )

    class Meta:
        verbose_name = "页面路由"
        verbose_name_plural = "页面路由"

    def __str__(self):
        return self.name


class GroupPagePermission(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name="用户组")
    page = models.ForeignKey(PageRoute, on_delete=models.CASCADE, verbose_name="页面")

    class Meta:
        unique_together = ("group", "page")
        verbose_name = "用户组页面权限"
        verbose_name_plural = "用户组页面权限"

    def __str__(self):
        return f"{self.group.name} - {self.page.name}"
