"""MemoUpdateTool 单元测试(dry_run + confirmed + 定位安全)。"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from smart_assistant.tools.memo_write_tools_v2 import MemoUpdateTool

User = get_user_model()


class TestMemoUpdateToolRegistry(TestCase):
    def test_tool_meta(self):
        tool = MemoUpdateTool()
        self.assertEqual(tool.name, "memo_update")
        self.assertEqual(tool.intent_type, "memo_update")
        self.assertEqual(tool.risk_level, "write")
        self.assertTrue(tool.require_confirmation)


class TestMemoUpdateToolDryRun(TestCase):
    def setUp(self):
        from memos.models import Memo

        self.user = User.objects.create_user(username="alice", password="x")
        self.memo = Memo.objects.create(user=self.user, title="明天开会", content="会议室A")
        self.tool = MemoUpdateTool()

    def test_dry_run_returns_draft_with_target(self):
        from smart_assistant.extractors.memo_update_extractor import UpdateParams

        ctx = {"dry_run": True, "user": self.user, "query": "把开会的备忘改成周会"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_update_params"
        ) as mock_extract:
            mock_extract.return_value = UpdateParams(target_title="开会", new_title="周会")
            result = self.tool.execute(query="把开会的备忘改成周会", context=ctx)
        self.assertTrue(result["found"])
        self.assertIn("draft", result)
        self.assertEqual(result["draft"]["fields"]["memo_id"], self.memo.id)
        self.assertEqual(result["draft"]["fields"]["new_title"], "周会")

    def test_dry_run_not_found_when_no_match(self):
        from smart_assistant.extractors.memo_update_extractor import UpdateParams

        ctx = {"dry_run": True, "user": self.user, "query": "把买菜备忘改一下"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_update_params"
        ) as mock_extract:
            mock_extract.return_value = UpdateParams(target_title="买菜", new_title="采购")
            result = self.tool.execute(query="把买菜备忘改一下", context=ctx)
        self.assertFalse(result["found"])
        self.assertIn("未找到", result["message"])

    def test_dry_run_rejects_multiple_candidates(self):
        from memos.models import Memo
        from smart_assistant.extractors.memo_update_extractor import UpdateParams

        Memo.objects.create(user=self.user, title="开会续会", content="x")
        ctx = {"dry_run": True, "user": self.user, "query": "把开会相关备忘改了"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_update_params"
        ) as mock_extract:
            mock_extract.return_value = UpdateParams(target_title="开会", new_title="周会")
            result = self.tool.execute(query="把开会相关备忘改了", context=ctx)
        self.assertFalse(result["found"])
        self.assertIn("找到", result["message"])

    def test_dry_run_missing_user_returns_not_found(self):
        ctx = {"dry_run": True, "user": None, "query": "改备忘"}
        result = self.tool.execute(query="改备忘", context=ctx)
        self.assertFalse(result["found"])


class TestMemoUpdateToolConfirmed(TestCase):
    def setUp(self):
        from memos.models import Memo

        self.user = User.objects.create_user(username="bob", password="x")
        self.other = User.objects.create_user(username="eve", password="x")
        self.memo = Memo.objects.create(user=self.user, title="买菜", content="番茄")
        self.other_memo = Memo.objects.create(user=self.other, title="买菜", content="别人的")
        self.tool = MemoUpdateTool()

    def test_confirmed_updates_memo(self):
        from memos.models import Memo

        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {
                "target_title": "买菜",
                "memo_id": self.memo.id,
                "new_title": "采购清单",
                "new_content": "番茄 鸡蛋",
                "new_reminder_time": None,
            },
        }
        result = self.tool.execute(query="把买菜备忘改成采购清单", context=ctx)
        self.assertTrue(result["found"])
        memo = Memo.objects.get(id=self.memo.id)
        self.assertEqual(memo.title, "采购清单")
        self.assertEqual(memo.content, "番茄 鸡蛋")

    def test_confirmed_does_not_touch_other_users_memo(self):
        from memos.models import Memo

        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {
                "target_title": "买菜",
                "memo_id": self.other_memo.id,  # 别人的 memo,归属校验应拒绝
                "new_title": "X",
            },
        }
        result = self.tool.execute(query="改备忘", context=ctx)
        self.assertFalse(result["found"])
        self.assertEqual(Memo.objects.get(id=self.other_memo.id).title, "买菜")

    def test_confirmed_draft_injection_skips_llm(self):
        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {"target_title": "买菜", "memo_id": self.memo.id, "new_title": "采购"},
        }
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_update_params"
        ) as mock_extract:
            result = self.tool.execute(query="改备忘", context=ctx)
            mock_extract.assert_not_called()
        self.assertTrue(result["found"])
