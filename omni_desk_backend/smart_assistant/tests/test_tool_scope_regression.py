"""R5-D1 scope 泄露回归测试。

红线:任何 read 工具在 SELF scope 下搜索他人数据必须返回空。
历史背景:旧路径 `Model.objects.filter` 曾造成「SELF scope 看到他人备忘录」
安全回归(C-1);本文件以黑盒方式对收敛工具锁定该约束——统一走工具公开入口
execute(query, context),不 mock 内部,让泄露(若存在)自然暴露为
「found=True 且含他人数据」。
"""

import pytest
from django.contrib.auth import get_user_model

from smart_assistant.tools.tool_context import ToolContext, SmartAssistantScope

User = get_user_model()


@pytest.fixture
def user_a(db):
    return User.objects.create_user(username="alice_self", password="x")


@pytest.fixture
def user_b(db):
    return User.objects.create_user(username="bob_other", password="x")


def _self_ctx(user):
    return ToolContext(user=user, scope=SmartAssistantScope.SELF)


class TestMemoScopeLeak:
    """SELF scope 用户搜索他人备忘录必须返回空。"""

    def test_self_scope_cannot_see_others_memo(self, db, user_a, user_b):
        from memos.models import Memo
        from smart_assistant.tools.memo_tool import MemoTool

        Memo.objects.create(user=user_b, title="机密会议纪要关键词XYZ", content="b的私人内容")
        result = MemoTool().execute(query="机密会议纪要关键词XYZ", context=_self_ctx(user_a))
        assert result.get("found") is False


class TestDocumentScopeLeak:
    """SELF scope 用户搜索他人文档模板必须返回空。"""

    def test_self_scope_cannot_see_others_template(self, db, user_a, user_b):
        from documents.models import DocumentTemplate
        from smart_assistant.tools.document_tool import DocumentTool

        DocumentTemplate.objects.create(name="B的合同模板ABC", owner=user_b, template_type="other")
        result = DocumentTool().execute(query="合同模板ABC", context=_self_ctx(user_a))
        assert result.get("found") is False


class TestNewsScopeLeak:
    """SELF scope 用户搜索他人发布的新闻必须返回空(personnel FK = 发布者)。"""

    def test_self_scope_cannot_see_others_news(self, db, user_a, user_b):
        import datetime

        from news.models import NewsArticle, NewsType
        from smart_assistant.tools.news_tool import NewsTool

        news_type = NewsType.objects.create(name="内部通报")
        NewsArticle.objects.create(
            title="绝密战略关键词QWE",
            news_type=news_type,
            publication_date=datetime.date(2026, 8, 1),
            personnel=user_b,  # 归属 user_b → SELF(user_a)scope 不可见
        )
        result = NewsTool().execute(query="绝密战略关键词QWE", context=_self_ctx(user_a))
        assert result.get("found") is False


class TestProjectScopeLeak:
    """SELF scope 用户搜索非本人管理的项目必须返回空。"""

    def test_self_scope_cannot_see_others_project(self, db, user_a, user_b):
        from projects.models import Project
        from smart_assistant.tools.project_tool import ProjectTool

        Project.objects.create(name="B的秘密项目ZXC", manager=user_b)
        result = ProjectTool().execute(query="秘密项目ZXC", context=_self_ctx(user_a))
        assert result.get("found") is False


class TestScheduleScopeLeak:
    """SELF scope 用户查询他人排班必须返回空(duty_person 经 Personnel 关联)。"""

    def test_self_scope_cannot_see_others_schedule(self, db, user_a, user_b):
        from datetime import date
        from events.models import Schedule
        from personnel.models import Personnel
        from smart_assistant.tools.schedule_tool import ScheduleTool

        # user_b 绑定 Personnel 后创建其名下排班;user_a 无 personnel → 任何排班都不可见
        p_b = Personnel.objects.create(name="鲍勃测试", user_account=user_b)
        Schedule.objects.create(duty_date=date(2026, 8, 30), duty_person=p_b)
        result = ScheduleTool().execute(query="2026-08-30 值班", context=_self_ctx(user_a))
        if result.get("found"):
            assert "鲍勃测试" not in str(result), f"SELF scope 泄露他人排班: {result}"
