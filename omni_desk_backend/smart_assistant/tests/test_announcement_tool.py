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

from datetime import timedelta

import pytest
from django.utils import timezone

from communication.models import Post
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
    Post.objects.create(title="本周例会通知", content="...", author=user)
    ctx = ToolContext(user=user)
    result = tool.execute("最近有什么公告", ctx)
    assert result["found"] is True
    assert result["count"] >= 1


@pytest.mark.django_db
def test_filters_expired_posts(tool, user):
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
    Post.objects.create(title="归档", content="x", is_archived=True)
    Post.objects.create(title="活跃", content="y", is_archived=False)
    ctx = ToolContext(user=user)
    result = tool.execute("公告", ctx)
    titles = [p["title"] for p in result["posts"]]
    assert "归档" not in titles


@pytest.mark.django_db
def test_keyword_in_title(tool, user):
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
    # m3: 断言消息内容含"未找到"和原 query
    assert "未找到" in result["message"]
    assert "不存在的关键词xyz123" in result["message"]


@pytest.mark.django_db
def test_limit_to_10_results(tool, user):
    for i in range(15):
        Post.objects.create(title=f"公告{i}", content="x")
    ctx = ToolContext(user=user)
    result = tool.execute("公告", ctx)
    assert result["count"] == 10
    assert len(result["posts"]) == 10


@pytest.mark.django_db
def test_author_none_fallback(tool, user):
    """m7: Post.author 为 None 时,返回 author 字段应 fallback 为 "系统"。"""
    Post.objects.create(title="无作者公告", content="x", author=None)
    ctx = ToolContext(user=user)
    result = tool.execute("无作者", ctx)
    assert result["found"] is True
    assert any(p["author"] == "系统" for p in result["posts"])


def test_required_auth_true(tool):
    assert tool.required_auth is True


def test_intent_type_is_announcement(tool):
    assert tool.intent_type == "announcement_query"
    assert tool.name == "announcement_query"


# =============================================================================
# 6. 新签名 execute(query=None, context=None, params=None, scope=None, qs=None)
#    — Task 7 跨模块汇总路径(2026-07-07)
#
# ⚠️ brief 已知 2 处会破坏实现的 bug(与 Task 5/6 同源模式):
# 1. `User.objects.create(username="alice")` — AbstractUser 必填 password,需 create_user()
# 2. `tool.execute({}, SmartAssistantScope.SELF, scoped)` — 3 个位置参数会映射到
#    (query, context, params),qs 落空走 fallback。新路径必须用 kwargs:
#    `tool.execute(params={}, scope=..., qs=...)`。
# =============================================================================


import pytest  # noqa: E402
from smart_assistant.scope import SmartAssistantScope  # noqa: E402
from smart_assistant.tools.tool_context import ToolContext  # noqa: E402
from smart_assistant.tools.announcement_tool import AnnouncementTool  # noqa: E402


@pytest.fixture
def tool():
    return AnnouncementTool()


@pytest.mark.django_db
def test_new_execute_filters_by_author(tool, db):
    """scope=SELF:只返回 ctx.user 发布的公告"""
    from django.contrib.auth import get_user_model
    from communication.models import Post

    User = get_user_model()
    # brief 用 .create(username=...) 在 AbstractUser 上会因缺 password 报错;
    # 改用 create_user 显式给密码
    alice = User.objects.create_user(username="alice", password="alice_pwd_123")
    bob = User.objects.create_user(username="bob", password="bob_pwd_123")
    Post.objects.create(title="A 写的", content="x", author=alice)
    Post.objects.create(title="B 写的", content="y", author=bob)

    ctx = ToolContext(user=alice, scope=SmartAssistantScope.SELF)
    base = tool.build_base_queryset()
    scoped = tool.get_queryset_for_scope(base, ctx)

    # 新路径必须用 kwargs(3 个位置参数会映射到 (query, context, params),qs 落空走 fallback)
    result = tool.execute(params={}, scope=SmartAssistantScope.SELF, qs=scoped)
    assert result["found"] is True
    titles = [p["title"] for p in result["posts"]]
    assert "A 写的" in titles
    assert "B 写的" not in titles
    assert result.get("module_label") == "公告"


@pytest.mark.django_db
def test_old_execute_still_works(tool, db):
    """旧签名仍工作"""
    from communication.models import Post

    Post.objects.create(title="x", content="y")
    ctx = ToolContext(user="u")
    result = tool.execute("公告", ctx)
    assert "found" in result


@pytest.mark.django_db
def test_scope_global_returns_all(tool, db):
    """scope=GLOBAL → 全部公告"""
    from communication.models import Post

    Post.objects.create(title="p1", content="c")
    Post.objects.create(title="p2", content="c")

    ctx = ToolContext(user="u", scope=SmartAssistantScope.GLOBAL)
    base = tool.build_base_queryset()
    scoped = tool.get_queryset_for_scope(base, ctx)

    # 新路径必须用 kwargs
    result = tool.execute(params={}, scope=SmartAssistantScope.GLOBAL, qs=scoped)
    assert result["count"] == 2


@pytest.mark.django_db
def test_module_label_in_result(tool, db):
    """新路径结果必须含 module_label='公告'"""
    from communication.models import Post

    Post.objects.create(title="x", content="c")

    ctx = ToolContext(user="u", scope=SmartAssistantScope.GLOBAL)
    base = tool.build_base_queryset()
    # 新路径必须用 kwargs
    result = tool.execute(params={}, scope=SmartAssistantScope.GLOBAL, qs=base)
    assert result.get("module_label") == "公告"
