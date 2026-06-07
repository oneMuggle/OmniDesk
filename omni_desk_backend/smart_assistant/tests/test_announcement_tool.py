"""AnnouncementTool 测试 - 通信公告查询工具.

对应交接文档任务 1.1:
- 基本查询:返回最近公告
- 过滤已过期公告
- 过滤已归档公告
- 关键词在标题/内容中匹配
- 空结果处理
- 限制 10 条结果
- required_auth 默认 True
- intent_type / name 验证
"""

import pytest

from smart_assistant.tools.tool_context import ToolContext
from smart_assistant.tools.announcement_tool import AnnouncementTool


@pytest.fixture
def tool():
    return AnnouncementTool()


@pytest.fixture
def user(db, admin_user_obj):
    return admin_user_obj


@pytest.mark.django_db
def test_basic_query_returns_recent_posts(tool, user):
    from communication.models import Post

    Post.objects.create(title="本周例会通知", content="...", author=user)
    ctx = ToolContext(user=user)
    result = tool.execute("最近有什么公告", ctx)
    assert result["found"] is True
    assert result["count"] >= 1


@pytest.mark.django_db
def test_filters_expired_posts(tool, user):
    from datetime import timedelta

    from django.utils import timezone

    from communication.models import Post

    past = timezone.now() - timedelta(days=10)
    Post.objects.create(title="已过期", content="x", expires_at=past)
    Post.objects.create(title="未过期", content="y")
    ctx = ToolContext(user=user)
    result = tool.execute("公告", ctx)
    titles = [p["title"] for p in result["posts"]]
    assert "已过期" not in titles
    assert "未过期" in titles


@pytest.mark.django_db
def test_filters_archived(tool, user):
    from communication.models import Post

    Post.objects.create(title="归档", content="x", is_archived=True)
    Post.objects.create(title="活跃", content="y", is_archived=False)
    ctx = ToolContext(user=user)
    result = tool.execute("公告", ctx)
    titles = [p["title"] for p in result["posts"]]
    assert "归档" not in titles


@pytest.mark.django_db
def test_keyword_in_title(tool, user):
    from communication.models import Post

    Post.objects.create(title="安全检查通知", content="...")
    Post.objects.create(title="排班调整", content="...")
    ctx = ToolContext(user=user)
    result = tool.execute("安全", ctx)
    assert any("安全" in p["title"] for p in result["posts"])


@pytest.mark.django_db
def test_empty_result_returns_not_found(tool, user):
    ctx = ToolContext(user=user)
    result = tool.execute("不存在的关键词xyz123", ctx)
    assert result["found"] is False
    assert "message" in result


@pytest.mark.django_db
def test_limit_to_10_results(tool, user):
    from communication.models import Post

    for i in range(15):
        Post.objects.create(title=f"公告{i}", content="x")
    ctx = ToolContext(user=user)
    result = tool.execute("公告", ctx)
    assert result["count"] == 10
    assert len(result["posts"]) == 10


def test_required_auth_true(tool):
    assert tool.required_auth is True


def test_intent_type_is_announcement(tool):
    assert tool.intent_type == "announcement_query"
    assert tool.name == "announcement_query"
