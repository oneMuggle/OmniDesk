"""为联培生编辑页增加独立页面权限。"""
from django.db import migrations


EDIT_PATH = "/joint-students/admin/students/:id/edit"


def add_edit_page_permission(apps, schema_editor):
    PageRoute = apps.get_model("permissions", "PageRoute")
    Group = apps.get_model("auth", "Group")
    GroupPagePermission = apps.get_model("permissions", "GroupPagePermission")

    route, _ = PageRoute.objects.get_or_create(
        path=EDIT_PATH,
        defaults={
            "name": "联培生-编辑联培生",
            "component": "StudentEditPage",
        },
    )
    group = Group.objects.get(name="联培生管理员")
    GroupPagePermission.objects.get_or_create(group=group, page=route)


def remove_edit_page_permission(apps, schema_editor):
    PageRoute = apps.get_model("permissions", "PageRoute")
    PageRoute.objects.filter(path=EDIT_PATH).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("joint_students", "0004_seed_page_permissions"),
    ]

    operations = [migrations.RunPython(add_edit_page_permission, remove_edit_page_permission)]
