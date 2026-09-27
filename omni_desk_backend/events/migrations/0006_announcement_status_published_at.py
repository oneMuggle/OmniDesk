from django.db import migrations, models
from django.db.models import F


def backfill_published_at(apps, schema_editor):
    """已有公告都视为已发布，发布时间取创建时间。"""
    Announcement = apps.get_model("events", "Announcement")
    Announcement.objects.filter(published_at__isnull=True).update(published_at=F("created_at"))


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0005_alter_announcement_created_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="announcement",
            name="status",
            field=models.CharField(
                choices=[("draft", "草稿"), ("published", "已发布")],
                db_index=True,
                default="published",
                max_length=20,
                verbose_name="状态",
            ),
        ),
        migrations.AddField(
            model_name="announcement",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="发布时间"),
        ),
        migrations.RunPython(backfill_published_at, migrations.RunPython.noop),
    ]
