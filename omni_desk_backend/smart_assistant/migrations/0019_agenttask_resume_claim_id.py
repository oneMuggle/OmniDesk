from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("smart_assistant", "0018_agentwritelog")]

    operations = [
        migrations.AddField(
            model_name="agenttask",
            name="resume_claim_id",
            field=models.UUIDField(
                blank=True,
                editable=False,
                null=True,
                verbose_name="恢复 worker claim",
            ),
        ),
    ]
