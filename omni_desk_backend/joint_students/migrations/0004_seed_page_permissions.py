"""为联培生管理员、考核专家组与联培生导师绑定页面权限。"""
from django.db import migrations


ADMIN_PATHS = [
    "/joint-students/admin/students",
    "/joint-students/admin/students/new",
    "/joint-students/admin/students/:id",
    "/joint-students/admin/reports",
    "/joint-students/admin/cycles",
    "/joint-students/admin/cycles/:id",
    "/joint-students/admin/stipends",
]
EXPERT_PATHS = ["/joint-students/expert/scoring"]
STUDENT_PATHS = [
    "/joint-students/student/reports",
    "/joint-students/student/reports/new",
    "/joint-students/student/stipends",
]
MENTOR_PATHS = ["/joint-students/mentor/overview"]


def create_groups_and_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    PageRoute = apps.get_model("permissions", "PageRoute")
    GroupPagePermission = apps.get_model("permissions", "GroupPagePermission")

    for name in ("联培生管理员", "考核专家组", "联培生学生", "联培生导师"):
        Group.objects.get_or_create(name=name)

    assignments = {
        "联培生管理员": ADMIN_PATHS,
        "考核专家组": EXPERT_PATHS,
        "联培生学生": STUDENT_PATHS,
        "联培生导师": MENTOR_PATHS,
    }
    for group_name, paths in assignments.items():
        group = Group.objects.get(name=group_name)
        for path in paths:
            page = PageRoute.objects.get(path=path)
            GroupPagePermission.objects.get_or_create(group=group, page=page)


def remove_groups_and_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    GroupPagePermission = apps.get_model("permissions", "GroupPagePermission")
    GroupPagePermission.objects.filter(
        group__name__in=["联培生管理员", "考核专家组", "联培生学生", "联培生导师"],
        page__path__in=ADMIN_PATHS + EXPERT_PATHS + STUDENT_PATHS + MENTOR_PATHS,
    ).delete()
    Group.objects.filter(name__in=["联培生学生", "联培生导师"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("joint_students", "0003_seed_page_routes"),
    ]
    operations = [migrations.RunPython(create_groups_and_permissions, remove_groups_and_permissions)]
