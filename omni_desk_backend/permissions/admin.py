from django.contrib import admin
from .models import PageRoute, GroupPagePermission

# Register your models here.
admin.site.register(PageRoute)
admin.site.register(GroupPagePermission)
