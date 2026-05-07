"""用户相关 Celery 任务。"""
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

CustomUser = get_user_model()


@shared_task
def cleanup_expired_guest_users():
    """清理超过 7 天未活跃的游客用户。"""
    threshold = timezone.now() - timedelta(days=7)
    qs = CustomUser.objects.filter(
        username__startswith='guest_',
        last_login__lte=threshold,
    )
    count, _ = qs.delete()
    return f'Deleted {count} expired guest users'
