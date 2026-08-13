"""MemoCreateTool 单元测试(dry_run + confirmed + 拒认二次确认外路径)。
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from smart_assistant.tools.memo_write_tools import MemoCreateTool

User = get_user_model()


class TestMemoCreateToolRegistry(TestCase):
    def test_tool_name(self):
        self.assertEqual(MemoCreateTool().name, "memo_create")

    def test_tool_intent_type(self):
        self.assertEqual(MemoCreateTool().intent_type, "memo_create")

    def test_tool_risk_level_is_write(self):
        self.assertEqual(MemoCreateTool().risk_level, "write")

    def test_tool_requires_confirmation(self):
        self.assertTrue(MemoCreateTool().require_confirmation)


class TestMemoCreateToolDryRun(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="x")
        self.tool = MemoCreateTool()

    def test_dry_run_returns_draft(self):
        ctx = {
            "dry_run": True,
            "user": self.user,
            "query": "提醒明天下午3点开会",
        }
        with patch(
            "smart_assistant.tools.memo_write_tools.extract_create_params"
        ) as mock_extract:
            from smart_assistant.extractors.memo_extractor import CreateParams

            mock_extract.return_value = CreateParams(
                title="开会", content="季度总结", reminder_time=None
            )
            result = self.tool.execute(query="提醒明天下午3点开会", ctx=ctx)
        self.assertTrue(result["found"])
        self.assertIn("draft", result)
        self.assertEqual(result["draft"]["fields"]["title"], "开会")

    def test_dry_run_returns_not_found_when_extractor_fails(self):
        ctx = {"dry_run": True, "user": self.user, "query": "ssss"}
        with patch(
            "smart_assistant.tools.memo_write_tools.extract_create_params"
        ) as mock_extract:
            mock_extract.return_value = None
            result = self.tool.execute(query="ssss", ctx=ctx)
        self.assertFalse(result["found"])


class TestMemoCreateToolConfirmed(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bob", password="x")
        self.tool = MemoCreateTool()

    def test_confirmed_persists_memo(self):
        from memos.models import Memo

        ctx = {"confirmed": True, "user": self.user, "query": "记一条备忘"}
        with patch(
            "smart_assistant.tools.memo_write_tools.extract_create_params"
        ) as mock_extract:
            from smart_assistant.extractors.memo_extractor import CreateParams

            mock_extract.return_value = CreateParams(
                title="买菜", content="番茄 鸡蛋", reminder_time=None
            )
            result = self.tool.execute(query="记一条备忘", ctx=ctx)
        self.assertTrue(result["found"])
        memo = Memo.objects.get(id=result["result"]["memo_id"])
        self.assertEqual(memo.user, self.user)
        self.assertEqual(memo.title, "买菜")
        self.assertFalse(memo.is_completed)

    def test_confirmed_missing_user_returns_not_found(self):
        ctx = {"confirmed": True, "user": None, "query": "记"}
        result = self.tool.execute(query="记", ctx=ctx)
        self.assertFalse(result["found"])


class TestMemoCreateToolFallbackPath(TestCase):
    """未带 dry_run / confirmed 标记的兜底路径(防御,理论上不到)。"""

    def test_fallback_returns_error(self):
        from django.contrib.auth.models import AnonymousUser

        tool = MemoCreateTool()
        ctx = {"user": AnonymousUser(), "query": "x"}
        result = tool.execute(query="x", ctx=ctx)
        self.assertFalse(result["found"])
