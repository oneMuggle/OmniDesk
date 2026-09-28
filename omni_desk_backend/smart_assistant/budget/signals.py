"""上限配置变更时失效缓存快照。"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from smart_assistant.models import LlmBudgetPolicy

from .policy import invalidate_cache


@receiver(post_save, sender=LlmBudgetPolicy, dispatch_uid="llm_budget_policy_saved")
@receiver(post_delete, sender=LlmBudgetPolicy, dispatch_uid="llm_budget_policy_deleted")
def _invalidate(**_kwargs):
    invalidate_cache()
