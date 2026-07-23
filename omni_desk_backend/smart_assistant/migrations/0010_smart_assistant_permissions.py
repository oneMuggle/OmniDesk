"""Create custom permissions for smart_assistant app.

Permissions: view_department, view_global (used by resolve_scope() in smart_assistant/scope.py).

这两个权限由 Task 9 的 check_tool_scopes 命令间接依赖:
  - resolve_scope() 通过 user.has_perm("smart_assistant.view_department") / .view_global 派生查询范围
  - 没有这 2 个 Permission 记录,has_perm() 永远返回 False,SELF 之外的权限提升永远走不到

本迁移使用 get_or_create 保证幂等(若已存在则跳过);reverse() 删除之。
"""
from django.db import migrations


def create_permissions(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    # smart_assistant app 包含 9 个 models(Django 已为每个 model 自动创建 ContentType)。
    # 注意:本数据迁移在 Django contenttypes post_migrate 信号之前运行,
    # 此时 smart_assistant 的 ContentType 行尚未被 Django 自动填充,
    # 所以必须用 get_or_create 而不是 get,否则会 DoesNotExist。
    # 选取 SmartAssistantSession(主会话模型)的 ContentType 作为这 2 条 app 级权限的归属。
    # 不可用 ContentType.objects.get(app_label="smart_assistant") —— 会 MultipleObjectsReturned。
    smart_assistant_ct, _ = ContentType.objects.get_or_create(
        app_label="smart_assistant",
        model="smartassistantsession",
    )

    Permission.objects.get_or_create(
        content_type=smart_assistant_ct,
        codename="view_department",
        defaults={"name": "Can view department-scoped smart assistant data"},
    )
    Permission.objects.get_or_create(
        content_type=smart_assistant_ct,
        codename="view_global",
        defaults={"name": "Can view all smart assistant data (admin)"},
    )


def reverse_permissions(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    Permission.objects.filter(
        content_type__app_label="smart_assistant",
        codename__in=["view_department", "view_global"],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("smart_assistant", "0009_alter_llmendpoint_api_key"),
    ]
    operations = [
        migrations.RunPython(create_permissions, reverse_permissions),
    ]
