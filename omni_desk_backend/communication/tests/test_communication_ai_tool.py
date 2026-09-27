"""AI 工具 communication_thread_query：可见范围与 /api/communication/posts/ 一致。"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from communication.ai_tools import CommunicationThreadQueryTool
from communication.models import Comment, Post
from smart_assistant.tools.tool_context import ToolContext

User = get_user_model()


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="comm_ai_alice", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="comm_ai_bob", password="x")


def _run(user, **params):
    return CommunicationThreadQueryTool().execute(context=ToolContext(user=user), params={"query": "帖子", **params})


@pytest.mark.django_db
class TestCommunicationThreadQueryTool:
    def test_visibility_matches_api(self, alice, bob):
        visible = Post.objects.create(title="食堂菜单讨论", content="大家觉得怎么样", author=bob)
        Post.objects.create(title="已归档帖子", content="旧内容", author=bob, is_archived=True)

        client = APIClient()
        client.force_authenticate(alice)
        resp = client.get("/api/communication/posts/")
        assert resp.status_code == 200
        body = resp.json()
        api_ids = sorted(p["id"] for p in (body["results"] if isinstance(body, dict) else body))

        result = _run(alice, limit=10)
        assert sorted(p["id"] for p in result["posts"]) == api_ids == [visible.id]

    def test_comments_and_counts(self, alice, bob):
        post = Post.objects.create(title="团建地点", content="投票", author=alice)
        for i in range(7):
            Comment.objects.create(post=post, author=bob, content=f"评论{i}")

        (item,) = _run(alice, post_id=post.id)["posts"]
        assert item["comment_count"] == 7
        # 最多带回 5 条最近评论，按时间正序展示
        assert [c["content"] for c in item["recent_comments"]] == [f"评论{i}" for i in range(2, 7)]
        assert item["url"] == f"/communication/{post.id}"

    def test_mine_only_and_keyword(self, alice, bob):
        mine = Post.objects.create(title="我的提问", content="打印机坏了", author=alice)
        Post.objects.create(title="别人的帖子", content="打印机", author=bob)

        assert [p["id"] for p in _run(alice, mine_only=True)["posts"]] == [mine.id]
        assert len(_run(alice, keyword="打印机")["posts"]) == 2

        legacy = CommunicationThreadQueryTool().execute("我发的帖子有人回复吗", {"user": alice})
        assert [p["id"] for p in legacy["posts"]] == [mine.id]

    def test_empty_and_anonymous(self, alice):
        assert _run(alice)["found"] is False
        assert CommunicationThreadQueryTool().execute("帖子", {"user": None})["found"] is False
