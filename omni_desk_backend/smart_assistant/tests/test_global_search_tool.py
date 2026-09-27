"""global_search 工具：复用联邦搜索 provider，范围与用户 scope 一致。"""

from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model

from memos.models import Memo
from search_federation.providers import SOURCE_CHOICES
from smart_assistant.scope import resolve_scope
from smart_assistant.tools.global_search_tool import SOURCE_ENUM, GlobalSearchTool
from smart_assistant.tools.registry import ToolRegistry
from smart_assistant.tools.tool_context import ToolContext

CustomUser = get_user_model()


@pytest.fixture
def users(db):
    alice = CustomUser.objects.create_user(username="gs_alice", password="p")
    bob = CustomUser.objects.create_user(username="gs_bob", password="p")
    Memo.objects.create(user=alice, title="季度复盘-alice")
    Memo.objects.create(user=bob, title="季度复盘-bob")
    return alice, bob


def test_registered_and_read_only():
    tool = ToolRegistry._tools["global_search"]
    assert isinstance(tool, GlobalSearchTool)
    assert tool.risk_level == "read"
    assert tool.require_confirmation is False
    # 不直接查模型：由 provider 复用原工具 scope
    assert tool.supports_scope_filter is False


def test_source_enum_matches_providers():
    assert tuple(SOURCE_ENUM) == SOURCE_CHOICES


def test_schema_validates_arguments():
    GlobalSearchTool.validate_arguments({"query": "x", "sources": ["memo"]})
    with pytest.raises(Exception):
        GlobalSearchTool.validate_arguments({"query": "x", "sources": ["evil"]})


@pytest.mark.django_db
class TestGlobalSearchExecute:
    def test_tool_context_respects_self_scope(self, users):
        alice, _ = users
        ctx = ToolContext(user=alice, scope=resolve_scope(alice))
        result = GlobalSearchTool().execute(query=None, context=ctx, params={"query": "季度复盘"})
        assert result["found"] is True
        assert [r["title"] for r in result["results"]] == ["季度复盘-alice"]
        assert result["by_source"] == {"memo": 1}

    def test_legacy_dict_context_resolves_scope(self, users):
        _, bob = users
        result = GlobalSearchTool().execute("季度复盘", {"history": [], "user": bob})
        assert [r["title"] for r in result["results"]] == ["季度复盘-bob"]

    def test_sources_filter(self, users):
        alice, _ = users
        ctx = ToolContext(user=alice, scope=resolve_scope(alice))
        result = GlobalSearchTool().execute(context=ctx, params={"query": "季度复盘", "sources": ["project"]})
        assert result["found"] is False

    def test_without_user_returns_not_found(self, users):
        assert GlobalSearchTool().execute("季度复盘", {"history": []})["found"] is False
        assert GlobalSearchTool().execute("季度复盘", None)["found"] is False
        anon = Mock(is_authenticated=False)
        assert GlobalSearchTool().execute("季度复盘", {"user": anon})["found"] is False

    def test_empty_query(self, users):
        alice, _ = users
        ctx = ToolContext(user=alice, scope=resolve_scope(alice))
        assert GlobalSearchTool().execute("  ", ctx)["found"] is False
