from django.contrib import admin

from .models import GroupPagePermission, PageRoute

# Register your models here.
admin.site.register(PageRoute)
admin.site.register(GroupPagePermission)
