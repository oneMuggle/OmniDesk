"""P0-D communication 作者隔离测试

此前 Post/Comment 仅 IsAuthenticated,任意用户可改删他人帖子/评论。
IsAuthorOrReadOnly 后:读放行,写/删仅限作者本人。
"""
import pytest
from rest_framework.test import APIClient

from communication.models import Comment, Post
from users.models import CustomUser


@pytest.fixture
def alice(db):
    return CustomUser.objects.create_user(username="alice_comm", password="pass12345")


@pytest.fixture
def bob(db):
    return CustomUser.objects.create_user(username="bob_comm", password="pass12345")


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestPostAuthorIsolation:
    def test_user_cannot_delete_others_post(self, alice, bob):
        post = Post.objects.create(title="alice 的帖子", content="内容", author=alice)

        resp = _client(bob).delete(f"/api/communication/posts/{post.pk}/")
        assert resp.status_code in (403, 404)
        assert Post.objects.filter(pk=post.pk).exists()

    def test_user_cannot_update_others_post(self, alice, bob):
        post = Post.objects.create(title="原标题", content="内容", author=alice)

        resp = _client(bob).patch(
            f"/api/communication/posts/{post.pk}/", {"title": "被篡改"}, format="json"
        )
        assert resp.status_code in (403, 404)
        post.refresh_from_db()
        assert post.title == "原标题"

    def test_author_can_delete_own_post(self, alice):
        post = Post.objects.create(title="自己的帖子", content="内容", author=alice)

        resp = _client(alice).delete(f"/api/communication/posts/{post.pk}/")
        assert resp.status_code == 204
        assert not Post.objects.filter(pk=post.pk).exists()

    def test_other_user_can_read_others_post(self, alice, bob):
        """读操作不受作者隔离影响(内部交流板块需全员可见)。"""
        post = Post.objects.create(title="公开帖子", content="内容", author=alice)

        resp = _client(bob).get(f"/api/communication/posts/{post.pk}/")
        assert resp.status_code == 200
        assert resp.data["title"] == "公开帖子"


@pytest.mark.django_db
class TestCommentAuthorIsolation:
    def test_user_cannot_delete_others_comment(self, alice, bob):
        post = Post.objects.create(title="帖子", content="内容", author=alice)
        comment = Comment.objects.create(post=post, author=alice, content="alice 的评论")

        resp = _client(bob).delete(f"/api/communication/posts/{post.pk}/comments/{comment.pk}/")
        assert resp.status_code in (403, 404)
        assert Comment.objects.filter(pk=comment.pk).exists()

    def test_author_can_delete_own_comment(self, alice, bob):
        post = Post.objects.create(title="帖子", content="内容", author=alice)
        comment = Comment.objects.create(post=post, author=bob, content="bob 的评论")

        resp = _client(bob).delete(f"/api/communication/posts/{post.pk}/comments/{comment.pk}/")
        assert resp.status_code == 204
        assert not Comment.objects.filter(pk=comment.pk).exists()
