"""AI 工具 document_library_query：可见范围与 /api/paperless/documents/ 一致，不调用 Paperless。"""

import itertools
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from paperless_proxy.ai_tools import DocumentLibraryQueryTool
from paperless_proxy.models import DocumentBinding, OutboxItem
from smart_assistant.scope import SmartAssistantScope
from smart_assistant.tools.tool_context import ToolContext

User = get_user_model()
_seq = itertools.count(1)


def _binding(owner, title, source_type="contract", paperless_id=None):
    n = next(_seq)
    return DocumentBinding.objects.create(
        source_type=source_type,
        source_id=n,
        paperless_id=paperless_id,
        paperless_checksum=f"sum{n}",
        owner=owner,
        title=title,
    )


def _run(user, scope=SmartAssistantScope.SELF, **params):
    return DocumentLibraryQueryTool().execute(
        context=ToolContext(user=user, scope=scope), params={"query": "文档库", **params}
    )


def _api_ids(user):
    client = APIClient()
    client.force_authenticate(user)
    resp = client.get("/api/paperless/documents/")
    assert resp.status_code == 200
    body = resp.json()
    return sorted(item["id"] for item in (body["results"] if isinstance(body, dict) else body))


@pytest.fixture
def alice(db):
    return User.objects.create_user(username="pl_ai_alice", password="x")


@pytest.fixture
def bob(db):
    return User.objects.create_user(username="pl_ai_bob", password="x")


@pytest.mark.django_db
class TestDocumentLibraryQueryTool:
    def test_regular_user_sees_only_own_same_as_api(self, alice, bob):
        own = _binding(alice, "采购合同 A")
        _binding(bob, "采购合同 B")
        ids = sorted(d["id"] for d in _run(alice, scope=SmartAssistantScope.GLOBAL)["documents"])
        assert ids == _api_ids(alice) == [own.id]

    def test_staff_sees_all_same_as_api(self, alice, bob):
        staff = User.objects.create_user(username="pl_ai_staff", password="x", is_staff=True)
        docs = [_binding(alice, "制度 1", "policy"), _binding(bob, "制度 2", "policy")]
        ids = sorted(d["id"] for d in _run(staff)["documents"])
        assert ids == _api_ids(staff) == sorted(d.id for d in docs)

    def test_filters_and_sync_status(self, alice):
        synced = _binding(alice, "年度采购合同", "contract", paperless_id=101)
        _binding(alice, "考勤制度", "policy")
        OutboxItem.objects.create(operation="upload", status="synced", binding=synced, payload={}, created_by=alice)

        result = _run(alice, keyword="采购")
        (item,) = result["documents"]
        assert item["title"] == "年度采购合同"
        assert item["source_type"] == "合同"
        assert item["synced"] is True
        assert item["sync_status"] == "已同步"
        assert result["url"] == "/documents-library"

        assert [d["title"] for d in _run(alice, source_type="policy")["documents"]] == ["考勤制度"]

    def test_does_not_call_paperless(self, alice):
        _binding(alice, "合同")
        with patch("paperless_proxy.services.client.PaperlessClient") as client_cls:
            _run(alice)
        client_cls.assert_not_called()

    def test_empty_and_anonymous(self, alice):
        assert _run(alice)["found"] is False
        assert DocumentLibraryQueryTool().execute("文档库", {"user": None})["found"] is False
