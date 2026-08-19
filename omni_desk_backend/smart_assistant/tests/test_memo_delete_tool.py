"""MemoDeleteTool 单元测试(destructive + 定位安全 + 归属校验)。"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from smart_assistant.tools.memo_write_tools_v2 import MemoDeleteTool

User = get_user_model()


class TestMemoDeleteToolRegistry(TestCase):
    def test_tool_meta(self):
        tool = MemoDeleteTool()
        self.assertEqual(tool.name, "memo_delete")
        self.assertEqual(tool.intent_type, "memo_delete")
        self.assertEqual(tool.risk_level, "destructive")
        self.assertTrue(tool.require_confirmation)


class TestMemoDeleteToolDryRun(TestCase):
    def setUp(self):
        from memos.models import Memo

        self.user = User.objects.create_user(username="alice", password="x")
        self.memo = Memo.objects.create(user=self.user, title="旧采购单")
        self.tool = MemoDeleteTool()

    def test_dry_run_returns_draft_with_warning(self):
        from smart_assistant.extractors.memo_delete_extractor import DeleteParams

        ctx = {"dry_run": True, "user": self.user, "query": "删掉旧采购单"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_delete_params"
        ) as mock_extract:
            mock_extract.return_value = DeleteParams(target_title="采购")
            result = self.tool.execute(query="删掉旧采购单", context=ctx)
        self.assertTrue(result["found"])
        self.assertEqual(result["draft"]["fields"]["memo_id"], self.memo.id)
        self.assertIn("永久删除", result["draft"]["summary"])
        self.assertIn("不可恢复", result["draft"]["summary"])

    def test_dry_run_not_found(self):
        from smart_assistant.extractors.memo_delete_extractor import DeleteParams

        ctx = {"dry_run": True, "user": self.user, "query": "删掉买菜备忘"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_delete_params"
        ) as mock_extract:
            mock_extract.return_value = DeleteParams(target_title="买菜")
            result = self.tool.execute(query="删掉买菜备忘", context=ctx)
        self.assertFalse(result["found"])

    def test_dry_run_rejects_multiple_candidates(self):
        from memos.models import Memo
        from smart_assistant.extractors.memo_delete_extractor import DeleteParams

        Memo.objects.create(user=self.user, title="采购清单 v2")
        ctx = {"dry_run": True, "user": self.user, "query": "删掉采购相关的"}
        with patch(
            "smart_assistant.tools.memo_write_tools_v2.extract_delete_params"
        ) as mock_extract:
            mock_extract.return_value = DeleteParams(target_title="采购")
            result = self.tool.execute(query="删掉采购相关的", context=ctx)
        self.assertFalse(result["found"])

    def test_dry_run_missing_user_returns_not_found(self):
        ctx = {"dry_run": True, "user": None, "query": "删备忘"}
        result = self.tool.execute(query="删备忘", context=ctx)
        self.assertFalse(result["found"])


class TestMemoDeleteToolConfirmed(TestCase):
    def setUp(self):
        from memos.models import Memo

        self.user = User.objects.create_user(username="bob", password="x")
        self.other = User.objects.create_user(username="eve", password="x")
        self.memo = Memo.objects.create(user=self.user, title="旧采购单")
        self.other_memo = Memo.objects.create(user=self.other, title="旧采购单")
        self.tool = MemoDeleteTool()

    def test_confirmed_deletes_own_memo(self):
        from memos.models import Memo

        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {"target_title": "采购", "memo_id": self.memo.id},
        }
        result = self.tool.execute(query="删掉旧采购单", context=ctx)
        self.assertTrue(result["found"])
        self.assertFalse(Memo.objects.filter(id=self.memo.id).exists())

    def test_confirmed_does_not_delete_others_memo(self):
        from memos.models import Memo

        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {"target_title": "采购", "memo_id": self.other_memo.id},
        }
        result = self.tool.execute(query="删掉旧采购单", context=ctx)
        self.assertFalse(result["found"])
        self.assertTrue(Memo.objects.filter(id=self.other_memo.id).exists())

    def test_confirmed_not_found(self):
        ctx = {
            "confirmed": True,
            "user": self.user,
            "draft": {"target_title": "不存在", "memo_id": 99999},
        }
        result = self.tool.execute(query="删掉不存在的", context=ctx)
        self.assertFalse(result["found"])
