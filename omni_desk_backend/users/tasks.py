"""用户相关 Celery 任务。"""

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

CustomUser = get_user_model()


@shared_task
def cleanup_expired_guest_users():
    """清理已过期的游客用户(guest_until 早于当前时间)。"""
    qs = CustomUser.objects.filter(
        username__startswith="guest_",
        guest_until__lt=timezone.now(),
    )
    count, _ = qs.delete()
    return f"Deleted {count} expired guest users"
