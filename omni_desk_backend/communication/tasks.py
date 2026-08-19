"""communication 定时任务(P0-6):过期帖子自动归档。

补全 ``Post.expires_at`` / ``is_archived`` 的自动化闭环——此前两字段已就位
但无任何归档逻辑,过期帖子仍停留在默认列表(views 过滤 is_archived=False)。
"""

from celery import shared_task
from django.utils import timezone
from observability import get_logger

logger = get_logger(__name__, "communication")


@shared_task
def archive_expired_posts():
    """把 ``expires_at <= now`` 且未归档的帖子批量置为已归档。

    使用 ``QuerySet.update()`` 单条 SQL 完成,无 N+1、无逐行实例化;
    仅命中 ``is_archived=False`` 的行,故 beat 重复执行幂等。归档后帖子
    从默认列表消失(views 过滤 is_archived=False)。

    Returns:
        int: 本次归档的帖子数量(供测试与日志观测)。
    """
    from .models import Post

    now = timezone.now()
    archived_count = Post.objects.filter(
        expires_at__isnull=False,
        expires_at__lte=now,
        is_archived=False,
    ).update(is_archived=True)

    if archived_count:
        logger.info("archive_expired_posts: 已归档 %d 条过期帖子", archived_count)
    return archived_count
