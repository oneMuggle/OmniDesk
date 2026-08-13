"""MemoCreateTool 单元测试(dry_run + confirmed + 兜底外路径)。

框架契约:execute 以 ``context=`` 关键字调用(与 execute_guarded 透传一致);
本测试全部使用 ``context=`` 调用,新增集成测试覆盖 orchestrator/chat.py replay
风格调用下 dry_run → confirmed 完整闭环。
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
            result = self.tool.execute(query="提醒明天下午3点开会", context=ctx)
        self.assertTrue(result["found"])
        self.assertIn("draft", result)
        self.assertEqual(result["draft"]["fields"]["title"], "开会")

    def test_dry_run_returns_not_found_when_extractor_fails(self):
        ctx = {"dry_run": True, "user": self.user, "query": "ssss"}
        with patch(
            "smart_assistant.tools.memo_write_tools.extract_create_params"
        ) as mock_extract:
            mock_extract.return_value = None
            result = self.tool.execute(query="ssss", context=ctx)
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
            result = self.tool.execute(query="记一条备忘", context=ctx)
        self.assertTrue(result["found"])
        memo = Memo.objects.get(id=result["result"]["memo_id"])
        self.assertEqual(memo.user, self.user)
        self.assertEqual(memo.title, "买菜")
        self.assertFalse(memo.is_completed)

    def test_confirmed_missing_user_returns_not_found(self):
        ctx = {"confirmed": True, "user": None, "query": "记"}
        result = self.tool.execute(query="记", context=ctx)
        self.assertFalse(result["found"])


class TestMemoCreateToolFallbackPath(TestCase):
    """未带 dry_run / confirmed 标记的兜底路径(防御,正常流程不可达,测试显式覆盖)。"""

    def test_fallback_returns_error(self):
        from django.contrib.auth.models import AnonymousUser

        tool = MemoCreateTool()
        ctx = {"user": AnonymousUser(), "query": "x"}
        result = tool.execute(query="x", context=ctx)
        self.assertFalse(result["found"])


class TestMemoCreateToolContextContract(TestCase):
    """以 ``context=`` 关键字调用(框架 execute_guarded 透传契约)的集成式测试。

    模拟 orchestrator C-2 风格 dry_run(context dict 含 user)→ chat.py replay
    风格 confirmed(context 注入 draft,不再二次调 LLM)完整闭环。
    """

    def setUp(self):
        self.user = User.objects.create_user(username="carol", password="x")
        self.tool = MemoCreateTool()

    def test_orchestrator_style_dry_run_then_confirmed(self):
        from memos.models import Memo
        from smart_assistant.extractors.memo_extractor import CreateParams

        # 1) orchestrator C-2 风格 dry_run:context= dict 含 user
        with patch(
            "smart_assistant.tools.memo_write_tools.extract_create_params"
        ) as mock_extract:
            mock_extract.return_value = CreateParams(
                title="周报", content="本周进展", reminder_time=None
            )
            dry_result = self.tool.execute(
                query="提醒写周报", context={"dry_run": True, "user": self.user}
            )
        self.assertTrue(dry_result["found"])
        self.assertIn("draft", dry_result)

        # 2) chat.py replay 风格 confirmed:context= 注入 draft,不再调 LLM
        draft_fields = dry_result["draft"]["fields"]
        with patch(
            "smart_assistant.tools.memo_write_tools.extract_create_params"
        ) as mock_extract:
            confirm_result = self.tool.execute(
                query="提醒写周报",
                context={
                    "confirmed": True,
                    "user": self.user,
                    "draft": draft_fields,
                },
            )
            mock_extract.assert_not_called()  # 走 draft 注入路径,不二次 LLM
        self.assertTrue(confirm_result["found"])
        memo = Memo.objects.get(id=confirm_result["result"]["memo_id"])
        self.assertEqual(memo.title, "周报")
        self.assertEqual(memo.user, self.user)

    def test_legacy_style_dry_run_with_injected_user(self):
        """I1 根治后:legacy 路径 dry_run context 注入 user,工具可用(不再 found=False)。"""
        from smart_assistant.extractors.memo_extractor import CreateParams

        # 模拟 orchestrator 367 行修复后的 context(带 user,无 draft)
        ctx = {"history": [], "dry_run": True, "user": self.user}
        with patch(
            "smart_assistant.tools.memo_write_tools.extract_create_params"
        ) as mock_extract:
            mock_extract.return_value = CreateParams(
                title="开会", content="下午3点", reminder_time=None
            )
            result = self.tool.execute(query="提醒明天下午3点开会", context=ctx)
        self.assertTrue(result["found"])
        self.assertIn("draft", result)
