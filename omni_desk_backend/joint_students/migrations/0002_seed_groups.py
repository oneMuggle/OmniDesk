"""创建联培生模块的 2 个固定 Group (空 Group, 成员由 admin 手动添加)。"""
from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="联培生管理员")
    Group.objects.get_or_create(name="考核专家组")


def remove_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["联培生管理员", "考核专家组"]).delete()


class Migration(migrations.Migration):
    dependencies = [("joint_students", "0001_initial")]
    operations = [migrations.RunPython(create_groups, remove_groups)]
