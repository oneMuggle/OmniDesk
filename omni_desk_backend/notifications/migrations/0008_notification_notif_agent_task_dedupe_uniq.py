from django.db import migrations, models


DEDUPLICATED_TYPE = "agent_task_result"


def deduplicate_agent_task_notifications(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    duplicate_groups = {}
    rows = Notification.objects.filter(
        type=DEDUPLICATED_TYPE
    ).exclude(dedupe_key="").order_by("user_id", "dedupe_key", "created_at", "pk")

    for notification in rows:
        group_key = (notification.user_id, notification.dedupe_key)
        retained = duplicate_groups.get(group_key)
        if retained is None:
            duplicate_groups[group_key] = notification
            continue
        retained.content = f"{retained.content}\n[追加] {notification.content}"
        retained.save(update_fields=["content", "updated_at"])
        notification.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0007_alter_notification_type"),
    ]

    operations = [
        migrations.RunPython(
            deduplicate_agent_task_notifications,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("type", "agent_task_result"),
                    models.Q(("dedupe_key", ""), _negated=True),
                ),
                fields=("user", "type", "dedupe_key"),
                name="notif_agent_task_dedupe_uniq",
            ),
        ),
    ]
