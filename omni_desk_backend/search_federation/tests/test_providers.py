# omni_desk_backend/search_federation/tests/test_providers.py
"""联邦搜索 provider：scope 隔离、失败时关闭、字段最小化。"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from compliance.models import ComplianceIssue
from documents.models import DocumentTemplate
from memos.models import Memo
from personnel.models import Personnel
from projects.models import Project
from search_federation.providers import PROVIDERS, SOURCE_CHOICES, search_internal
from smart_assistant.scope import SmartAssistantScope, resolve_scope
from smart_assistant.tools.tool_context import ToolContext

CustomUser = get_user_model()


def _ctx(user):
    return ToolContext(user=user, scope=resolve_scope(user))


@pytest.fixture
def alice(db):
    return CustomUser.objects.create_user(username="alice", password="p")


@pytest.fixture
def bob(db):
    return CustomUser.objects.create_user(username="bob", password="p")


@pytest.fixture
def global_user(db):
    user = CustomUser.objects.create_user(username="auditor", password="p")
    user.user_permissions.add(Permission.objects.get(codename="view_global", content_type__app_label="smart_assistant"))
    return CustomUser.objects.get(pk=user.pk)  # 刷新权限缓存


@pytest.fixture
def data(alice, bob):
    alice_person = Personnel.objects.create(name="联邦甲", department="技术部", phone_number="13800000000")
    bob_person = Personnel.objects.create(name="联邦乙", department="技术部", phone_number="13900000000")
    alice.personnel = alice_person
    alice.save(update_fields=["personnel"])
    bob.personnel = bob_person
    bob.save(update_fields=["personnel"])

    alice_project = Project.objects.create(name="联邦项目A", description="Alice 负责", manager=alice)
    bob_project = Project.objects.create(name="联邦项目B", description="Bob 负责", manager=bob)
    return {
        "alice_memo": Memo.objects.create(user=alice, title="联邦备忘-甲", content="alice 的内容"),
        "bob_memo": Memo.objects.create(user=bob, title="联邦备忘-乙", content="bob 的内容"),
        "deleted_memo": Memo.objects.create(user=alice, title="联邦备忘-已删", is_deleted=True),
        "alice_person": alice_person,
        "bob_person": bob_person,
        "alice_project": alice_project,
        "bob_project": bob_project,
        "alice_issue": ComplianceIssue.objects.create(
            project=alice_project, issue_type="不规范", description="联邦检查问题一", location="第3页"
        ),
        "bob_issue": ComplianceIssue.objects.create(
            project=bob_project, issue_type="其他", description="联邦检查问题二"
        ),
        "alice_doc": DocumentTemplate.objects.create(
            name="联邦模板甲", template_type="meeting_minutes", content="x", owner=alice
        ),
        "bob_doc": DocumentTemplate.objects.create(
            name="联邦模板乙", template_type="meeting_minutes", content="x", owner=bob
        ),
    }


def _ids(results, source):
    return {r["id"] for r in results if r["source"] == source}


@pytest.mark.django_db
class TestSearchInternalScope:
    def test_self_scope_only_returns_own_records(self, alice, data):
        ctx = _ctx(alice)
        assert ctx.scope == SmartAssistantScope.SELF

        results = search_internal(ctx, "联邦")

        assert _ids(results, "memo") == {data["alice_memo"].pk}
        assert _ids(results, "project") == {data["alice_project"].pk}
        assert _ids(results, "personnel") == {data["alice_person"].pk}
        assert _ids(results, "compliance") == {data["alice_issue"].pk}
        assert _ids(results, "document") == {data["alice_doc"].pk}

    def test_other_user_cannot_see_alice(self, bob, data):
        results = search_internal(_ctx(bob), "甲")
        assert _ids(results, "memo") == set()
        assert _ids(results, "personnel") == set()
        assert _ids(results, "document") == set()

    def test_global_scope_sees_everything_but_soft_deleted(self, global_user, data):
        ctx = _ctx(global_user)
        assert ctx.scope == SmartAssistantScope.GLOBAL

        results = search_internal(ctx, "联邦")

        assert _ids(results, "memo") == {data["alice_memo"].pk, data["bob_memo"].pk}
        assert data["deleted_memo"].pk not in _ids(results, "memo")
        assert _ids(results, "project") == {data["alice_project"].pk, data["bob_project"].pk}
        assert len(_ids(results, "personnel")) == 2

    def test_searches_secondary_fields(self, alice, data):
        results = search_internal(_ctx(alice), "第3页")
        assert _ids(results, "compliance") == {data["alice_issue"].pk}


@pytest.mark.django_db
class TestSearchInternalResultShape:
    def test_results_are_minimal_and_routable(self, global_user, alice, data):
        results = search_internal(_ctx(global_user), "联邦")
        assert results
        for item in results:
            assert set(item) == {"source", "id", "title", "subtitle", "url"}
            assert item["url"].startswith("/")
        # 不泄露敏感字段
        assert "13800000000" not in str(results)

        person = next(r for r in results if r["id"] == data["alice_person"].pk and r["source"] == "personnel")
        assert person["url"] == f"/control-panel/personnel/{data['alice_person'].pk}"

    def test_own_personnel_links_to_me_page(self, alice, data):
        results = search_internal(_ctx(alice), "联邦甲")
        person = next(r for r in results if r["source"] == "personnel")
        assert person["url"] == "/me/personnel"


@pytest.mark.django_db
class TestSearchInternalArguments:
    def test_empty_query_or_missing_user_returns_empty(self, alice, data):
        assert search_internal(_ctx(alice), "   ") == []
        assert search_internal(None, "联邦") == []
        assert search_internal(ToolContext(user=None), "联邦") == []

    def test_sources_filter(self, alice, data):
        results = search_internal(_ctx(alice), "联邦", sources=["memo"])
        assert {r["source"] for r in results} == {"memo"}

    def test_limit_is_clamped(self, global_user, data):
        for i in range(30):
            Memo.objects.create(user=global_user, title=f"批量联邦{i}")
        results = search_internal(_ctx(global_user), "批量联邦", sources=["memo"], limit=999)
        assert len(results) == 20
        assert len(search_internal(_ctx(global_user), "批量联邦", sources=["memo"], limit="bad")) == 5

    def test_source_choices_match_providers(self):
        assert SOURCE_CHOICES == tuple(p.source for p in PROVIDERS)
        assert set(SOURCE_CHOICES) == {"project", "memo", "personnel", "compliance", "document"}


@pytest.mark.django_db
class TestSearchInternalFailClosed:
    def test_missing_tool_skips_provider(self, alice, data):
        with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=None):
            assert search_internal(_ctx(alice), "联邦") == []

    def test_provider_error_is_isolated(self, alice, data):
        from smart_assistant.tools.memo_tool import MemoTool

        with patch.object(MemoTool, "build_base_queryset", side_effect=RuntimeError("boom")):
            results = search_internal(_ctx(alice), "联邦")
        assert _ids(results, "memo") == set()
        assert _ids(results, "project") == {data["alice_project"].pk}

    def test_tool_without_scope_support_is_skipped(self, alice, data):
        class NoScopeTool:
            supports_scope_filter = False

            def scoped_queryset(self, ctx):  # pragma: no cover - 不应被调用
                raise AssertionError("不应回退到无 scope 查询")

        with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=NoScopeTool()):
            assert search_internal(_ctx(alice), "联邦") == []
