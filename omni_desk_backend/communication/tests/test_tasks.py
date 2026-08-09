"""Tests for communication.tasks — P0-6 过期帖子自动归档."""

from datetime import timedelta

import pytest
from django.utils import timezone

from communication.models import Post
from communication.tasks import archive_expired_posts
from users.models import CustomUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username="comm_task_user", password="pass12345")


def _make_post(title, expires_at, **kwargs):
    return Post.objects.create(title=title, content="内容", expires_at=expires_at, **kwargs)


class TestArchiveExpiredPosts:
    """archive_expired_posts 批量归档过期帖子."""

    def test_expired_post_archived(self):
        """expires_at 已过且未归档 → 置为已归档,返回 1"""
        _make_post("过期帖", timezone.now() - timedelta(hours=1))
        assert archive_expired_posts() == 1
        assert Post.objects.get(title="过期帖").is_archived is True

    def test_future_post_not_archived(self):
        """expires_at 未到 → 不归档"""
        _make_post("未来帖", timezone.now() + timedelta(hours=1))
        assert archive_expired_posts() == 0
        assert Post.objects.get(title="未来帖").is_archived is False

    def test_no_expiry_not_archived(self):
        """expires_at 为空 → 永不自动归档"""
        _make_post("无期限帖", None)
        assert archive_expired_posts() == 0
        assert Post.objects.get(title="无期限帖").is_archived is False

    def test_already_archived_not_recounted(self):
        """已归档的过期帖 → 幂等,不重复计数"""
        _make_post("已归档帖", timezone.now() - timedelta(hours=1), is_archived=True)
        assert archive_expired_posts() == 0

    def test_idempotent_across_runs(self):
        """重复执行 → 第二次返回 0"""
        _make_post("帖A", timezone.now() - timedelta(hours=1))
        _make_post("帖B", timezone.now() - timedelta(hours=2))
        assert archive_expired_posts() == 2
        assert archive_expired_posts() == 0
        assert Post.objects.filter(is_archived=True).count() == 2

    def test_mixed_posts_only_expired_archived(self, user):
        """混合场景:仅过期未归档的被归档"""
        _make_post("过期1", timezone.now() - timedelta(minutes=5))
        _make_post("未来1", timezone.now() + timedelta(days=1))
        _make_post("无期限1", None)
        _make_post("已归档1", timezone.now() - timedelta(minutes=5), is_archived=True)
        assert archive_expired_posts() == 1
        assert Post.objects.filter(is_archived=True).count() == 2  # 过期1 + 已归档1
