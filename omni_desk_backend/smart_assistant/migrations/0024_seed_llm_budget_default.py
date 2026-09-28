"""预算与配额：建出全员默认上限（0 / 0 = 只统计不限制，只读阈值 80%）。"""

from django.db import migrations


def seed(apps, schema_editor):
    LlmBudgetPolicy = apps.get_model("smart_assistant", "LlmBudgetPolicy")
    LlmBudgetPolicy.objects.get_or_create(
        scope="default",
        defaults={"daily_token_limit": 0, "daily_call_limit": 0, "soft_limit_percent": 80, "note": "全员默认"},
    )


def unseed(apps, schema_editor):
    apps.get_model("smart_assistant", "LlmBudgetPolicy").objects.filter(scope="default").delete()


class Migration(migrations.Migration):
    dependencies = [("smart_assistant", "0023_llm_budget")]

    operations = [migrations.RunPython(seed, unseed)]
