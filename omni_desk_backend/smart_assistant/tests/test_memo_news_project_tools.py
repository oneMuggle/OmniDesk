"""MemoTool/NewsTool/ProjectTool 备忘录/新闻/项目搜索测试.

对应交接文档任务 A.5:
- memo_tool:参数解析、空结果、异常
- news_tool:参数解析、空结果、异常
- project_tool:参数解析、空结果、异常

3 个 tool 字段全部对齐,无 bug,所有测试可正常 pass。
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase

from smart_assistant.tools.memo_tool import MemoTool
from smart_assistant.tools.news_tool import NewsTool
from smart_assistant.tools.project_tool import ProjectTool


# =============================================================================
# 1. 基本属性测试
# =============================================================================


class TestToolProperties(TestCase):
    """3 个 tool 的元数据."""

    def test_memo_tool_name(self):
        self.assertEqual(MemoTool().name, "memo_query")

    def test_memo_tool_intent_type(self):
        self.assertEqual(MemoTool().intent_type, "memo_query")

    def test_memo_tool_description(self):
        self.assertIn("备忘录", MemoTool().description)

    def test_news_tool_name(self):
        self.assertEqual(NewsTool().name, "news_search")

    def test_news_tool_intent_type(self):
        self.assertEqual(NewsTool().intent_type, "news_search")

    def test_news_tool_description(self):
        self.assertIn("新闻", NewsTool().description)

    def test_project_tool_name(self):
        self.assertEqual(ProjectTool().name, "project_status")

    def test_project_tool_intent_type(self):
        self.assertEqual(ProjectTool().intent_type, "project_status")

    def test_project_tool_description(self):
        self.assertIn("项目", ProjectTool().description)

    def test_all_tools_schema_valid(self):
        """所有 tool 的 schema 应有 name/description/intent_type."""
        for tool_cls in [MemoTool, NewsTool, ProjectTool]:
            tool = tool_cls()
            schema = tool.get_schema()
            self.assertEqual(schema["name"], tool.name)
            self.assertEqual(schema["description"], tool.description)
            self.assertEqual(schema["intent_type"], tool.intent_type)


# =============================================================================
# 2. 关键词清理测试
# =============================================================================


class TestKeywordCleaning(TestCase):
    """3 个 tool 各自清理停用词."""

    @patch("smart_assistant.tools.memo_tool.Memo")
    def test_memo_strips_stopwords(self, mock_memo):
        """MemoTool 去除"搜索/查找/备忘录/便签"."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_memo.objects.filter.return_value.select_related.return_value = mock_qs

        MemoTool().execute("搜索查找备忘录便签内容")

        call_args = mock_memo.objects.filter.call_args
        self.assertEqual(call_args.kwargs.get("title__icontains"), "内容")

    @patch("smart_assistant.tools.news_tool.NewsArticle")
    def test_news_strips_stopwords(self, mock_news):
        """NewsTool 去除"搜索/查找/新闻/通知"."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_news.objects.filter.return_value.select_related.return_value = mock_qs

        NewsTool().execute("搜索查找新闻通知标题")

        call_args = mock_news.objects.filter.call_args
        self.assertEqual(call_args.kwargs.get("title__icontains"), "标题")

    @patch("smart_assistant.tools.project_tool.Project")
    def test_project_strips_stopwords(self, mock_project):
        """ProjectTool 去除"搜索/查找/项目"."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_project.objects.filter.return_value.select_related.return_value = mock_qs

        ProjectTool().execute("搜索查找项目内容")

        call_args = mock_project.objects.filter.call_args
        self.assertEqual(call_args.kwargs.get("name__icontains"), "内容")


# =============================================================================
# 3. 查询结果场景
# =============================================================================


class TestMemoToolResults(TestCase):
    """MemoTool 返回结果的字段结构."""

    def setUp(self):
        self.tool = MemoTool()

    @patch("smart_assistant.tools.memo_tool.Memo")
    def test_no_memo_returns_not_found(self, mock_memo):
        """无匹配备忘录时,found=False."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_memo.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute("搜索 XYZ-不存在的备忘录")

        self.assertFalse(result["found"])
        self.assertIn("message", result)
        # 工具清理"备忘录"停用词,message 含清理后关键词 "XYZ-不存在的"
        self.assertIn("XYZ-不存在的", result["message"])

    @patch("smart_assistant.tools.memo_tool.Memo")
    def test_matched_memo_returns_list(self, mock_memo):
        """匹配备忘录时返回列表."""
        mock_m = MagicMock()
        mock_m.title = "重要提醒"
        mock_m.content = "这是一条重要的提醒内容,超过 100 字需要被截断。" * 5
        mock_m.user = MagicMock(username="alice")
        mock_m.is_completed = False
        mock_m.reminder_time = None
        mock_m.created_at = datetime(2026, 5, 1, 10, 0, 0)

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(side_effect=lambda: iter([mock_m]))
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_memo.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute("搜索重要提醒")

        self.assertTrue(result["found"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["memos"][0]["title"], "重要提醒")
        self.assertEqual(result["memos"][0]["user"], "alice")
        self.assertIn("...", result["memos"][0]["content"], "长内容应被截断")
        self.assertEqual(result["memos"][0]["is_completed"], False)
        self.assertEqual(result["memos"][0]["reminder_time"], "无提醒")

    @patch("smart_assistant.tools.memo_tool.Memo")
    def test_short_content_not_truncated(self, mock_memo):
        """短内容(<100 字)不应被截断."""
        mock_m = MagicMock()
        mock_m.title = "短便签"
        mock_m.content = "短内容"  # 4 字
        mock_m.user = MagicMock(username="alice")
        mock_m.is_completed = True
        mock_m.reminder_time = datetime(2026, 6, 6, 9, 0, 0)
        mock_m.created_at = datetime(2026, 6, 6, 8, 0, 0)

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(side_effect=lambda: iter([mock_m]))
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_memo.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute("搜索短便签")

        self.assertEqual(result["memos"][0]["content"], "短内容")
        self.assertNotIn("...", result["memos"][0]["content"])
        self.assertEqual(result["memos"][0]["reminder_time"], "2026-06-06 09:00:00")

    @patch("smart_assistant.tools.memo_tool.Memo")
    def test_null_user_fallback(self, mock_memo):
        """memo.user 为 None 时,user 字段显示'未知'."""
        mock_m = MagicMock()
        mock_m.title = "无主便签"
        mock_m.content = "内容"
        mock_m.user = None
        mock_m.is_completed = False
        mock_m.reminder_time = None
        mock_m.created_at = datetime(2026, 5, 1)

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(side_effect=lambda: iter([mock_m]))
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_memo.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute("搜索无主便签")

        self.assertEqual(result["memos"][0]["user"], "未知")


class TestNewsToolResults(TestCase):
    """NewsTool 返回结果的字段结构."""

    def setUp(self):
        self.tool = NewsTool()

    @patch("smart_assistant.tools.news_tool.NewsArticle")
    def test_no_news_returns_not_found(self, mock_news):
        """无匹配新闻时,found=False."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_news.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute("搜索 XYZ-不存在的新闻")

        self.assertFalse(result["found"])
        self.assertIn("message", result)
        # 工具清理"新闻"停用词,message 含清理后关键词 "XYZ-不存在的"
        self.assertIn("XYZ-不存在的", result["message"])

    @patch("smart_assistant.tools.news_tool.NewsArticle")
    def test_matched_news_returns_list(self, mock_news):
        """匹配新闻时返回列表."""
        mock_news_type = MagicMock()
        mock_news_type.name = "技术资讯"

        mock_a = MagicMock()
        mock_a.title = "AI 技术突破"
        mock_a.link = "https://example.com/news/1"
        mock_a.publication_date = date(2026, 5, 1)
        mock_a.news_type = mock_news_type
        mock_a.personnel = MagicMock(username="bob")

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(side_effect=lambda: iter([mock_a]))
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_news.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute("搜索 AI")

        self.assertTrue(result["found"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["articles"][0]["title"], "AI 技术突破")
        self.assertEqual(result["articles"][0]["link"], "https://example.com/news/1")
        self.assertEqual(result["articles"][0]["news_type"], "技术资讯")
        self.assertEqual(result["articles"][0]["personnel"], "bob")

    @patch("smart_assistant.tools.news_tool.NewsArticle")
    def test_null_news_type_and_personnel_fallback(self, mock_news):
        """news_type/personnel 为 None 时,显示'未分类'/'未知'."""
        mock_a = MagicMock()
        mock_a.title = "无元数据新闻"
        mock_a.link = "https://example.com/news/2"
        mock_a.publication_date = date(2026, 5, 2)
        mock_a.news_type = None  # 关键
        mock_a.personnel = None  # 关键

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(side_effect=lambda: iter([mock_a]))
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_news.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute("搜索无元数据")

        self.assertEqual(result["articles"][0]["news_type"], "未分类")
        self.assertEqual(result["articles"][0]["personnel"], "未知")


class TestProjectToolResults(TestCase):
    """ProjectTool 返回结果的字段结构."""

    def setUp(self):
        self.tool = ProjectTool()

    @patch("smart_assistant.tools.project_tool.Project")
    def test_no_project_returns_not_found(self, mock_project):
        """无匹配项目时,found=False."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_project.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute("搜索 XYZ-不存在的项目")

        self.assertFalse(result["found"])
        self.assertIn("message", result)
        # 工具清理"项目"停用词,message 含清理后关键词 "XYZ-不存在的"
        self.assertIn("XYZ-不存在的", result["message"])

    @patch("smart_assistant.tools.project_tool.Project")
    def test_matched_project_returns_list(self, mock_project):
        """匹配项目时返回列表."""
        mock_p = MagicMock()
        mock_p.name = "OmniDesk 开发"
        mock_p.description = "公司内部办公管理系统开发项目"
        mock_p.manager = MagicMock(username="charlie")
        mock_p.status = "进行中"
        mock_p.start_date = date(2026, 1, 1)
        mock_p.end_date = date(2026, 12, 31)

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(side_effect=lambda: iter([mock_p]))
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_project.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute("搜索 OmniDesk")

        self.assertTrue(result["found"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["projects"][0]["name"], "OmniDesk 开发")
        self.assertEqual(result["projects"][0]["manager"], "charlie")
        self.assertEqual(result["projects"][0]["status"], "进行中")
        self.assertEqual(result["projects"][0]["start_date"], "2026-01-01")
        self.assertEqual(result["projects"][0]["end_date"], "2026-12-31")

    @patch("smart_assistant.tools.project_tool.Project")
    def test_null_manager_fallback(self, mock_project):
        """project.manager 为 None 时,显示'未指定'."""
        mock_p = MagicMock()
        mock_p.name = "无主项目"
        mock_p.description = "无负责人的项目"
        mock_p.manager = None
        mock_p.status = "已暂停"
        mock_p.start_date = date(2026, 1, 1)
        mock_p.end_date = None  # 关键:end_date 为空

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(side_effect=lambda: iter([mock_p]))
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_project.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute("搜索无主项目")

        self.assertEqual(result["projects"][0]["manager"], "未指定")
        self.assertEqual(result["projects"][0]["end_date"], "未设置")

    @patch("smart_assistant.tools.project_tool.Project")
    def test_long_description_truncated(self, mock_project):
        """长 description 应被截断到 100 字."""
        mock_p = MagicMock()
        mock_p.name = "Long"
        mock_p.description = "很长的描述" * 30  # 远超过 100 字
        mock_p.manager = MagicMock(username="alice")
        mock_p.status = "进行中"
        mock_p.start_date = None
        mock_p.end_date = None

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(side_effect=lambda: iter([mock_p]))
        mock_qs.__getitem__ = MagicMock(return_value=mock_qs)
        mock_project.objects.filter.return_value.select_related.return_value = mock_qs

        result = self.tool.execute("搜索 Long")

        # 100 字截断 + "..." 后缀
        self.assertTrue(result["projects"][0]["description"].endswith("..."))
        # 实际内容(去除 "...")应 <= 100 字
        content_without_suffix = result["projects"][0]["description"][:-3]
        self.assertLessEqual(len(content_without_suffix), 100)


# =============================================================================
# 4. 真实 DB 场景(3 个 tool 字段全对齐,无 bug,所有测试应 pass)
# =============================================================================


@pytest.mark.django_db
class TestMemoNewsProjectDatabase:
    """真实 DB 场景:3 个 tool 字段全对齐,所有测试应 pass."""

    @pytest.fixture
    def memo_tool(self):
        return MemoTool()

    @pytest.fixture
    def news_tool(self):
        return NewsTool()

    @pytest.fixture
    def project_tool(self):
        return ProjectTool()

    def test_memo_create_and_search(self, db, memo_tool, admin_user_obj):
        """创建备忘录并搜索."""
        from memos.models import Memo

        Memo.objects.create(
            user=admin_user_obj,
            title="项目计划",
            content="Q3 项目计划内容",
            is_completed=False,
        )

        result = memo_tool.execute("搜索项目计划")

        assert result["found"] is True
        assert any(m["title"] == "项目计划" for m in result["memos"])

    def test_memo_no_match_returns_not_found(self, db, memo_tool, admin_user_obj):
        """无匹配备忘录返回 found=False."""
        from memos.models import Memo

        Memo.objects.create(
            user=admin_user_obj,
            title="唯一标题",
            content="内容",
        )

        result = memo_tool.execute("搜索不存在的关键词")

        assert result["found"] is False

    def test_news_create_and_search(self, db, news_tool, admin_user_obj):
        """创建新闻并搜索."""
        from news.models import NewsArticle, NewsType

        news_type = NewsType.objects.create(name="技术资讯")
        NewsArticle.objects.create(
            title="GPT-5 发布",
            link="https://example.com/gpt5",
            publication_date=date(2026, 6, 1),
            personnel=admin_user_obj,
            news_type=news_type,
        )

        result = news_tool.execute("搜索 GPT")

        assert result["found"] is True
        assert any(a["title"] == "GPT-5 发布" for a in result["articles"])

    def test_project_create_and_search(self, db, project_tool, admin_user_obj):
        """创建项目并搜索."""
        from projects.models import Project

        Project.objects.create(
            name="智能助手优化",
            description="v0.6.0 优化",
            status="进行中",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            manager=admin_user_obj,
        )

        result = project_tool.execute("搜索智能助手")

        assert result["found"] is True
        assert any(p["name"] == "智能助手优化" for p in result["projects"])

    def test_project_search_by_name_filter(self, db, project_tool, admin_user_obj):
        """按 name 搜索(不能直接按 status 过滤)."""
        from projects.models import Project

        Project.objects.create(name="已暂停项目A", status="已暂停", description="A")
        Project.objects.create(name="已暂停项目B", status="已暂停", description="B")
        Project.objects.create(name="进行中项目C", status="进行中", description="C")

        result = project_tool.execute("搜索已暂停")

        # tool 按 name 搜索,匹配 2 个已暂停项目
        assert result["found"] is True
        names = [p["name"] for p in result["projects"]]
        assert "已暂停项目A" in names
        assert "已暂停项目B" in names
        assert "进行中项目C" not in names
