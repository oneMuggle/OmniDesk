"""S4-2 知识自动入库：入库内容、同步、触发、对账、检索按权限过滤、管理端接口。"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

from events.models import Announcement
from paperless_proxy.models import DocumentBinding
from ragflow_service.models import RagflowConfig
from smart_assistant.agent.rag_router import RAGRouter
from smart_assistant.knowledge import sync as sync_module
from smart_assistant.knowledge.acl import filter_chunks
from smart_assistant.knowledge.content import ContentNotReady, build_announcement, build_paperless, html_to_text
from smart_assistant.knowledge.sync import MAX_ATTEMPTS, reconcile, reconcile_candidates, sync_source
from smart_assistant.models import KnowledgeSource
from smart_assistant.tools.rag_tool import RAGTool

API = "/api/smart-assistant/knowledge-sources"
ANN_URL = "/api/events/announcements/"
DATASET = "ds-ingest"
GET_DOC = "paperless_proxy.services.client.PaperlessClient.get_document"
TASK_DELAY = "smart_assistant.tasks.sync_knowledge_source.delay"


def make_user(username, group=None, **extra):
    user = get_user_model().objects.create_user(username=username, password="x", **extra)
    if group:
        user.groups.add(Group.objects.get_or_create(name=group)[0])
    return user


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def make_binding(owner, title="采购合同", paperless_id=101, source_id=1):
    return DocumentBinding.objects.create(
        source_type="contract",
        source_id=source_id,
        paperless_id=paperless_id,
        paperless_checksum="abc",
        owner=owner,
        title=title,
    )


def fake_client(doc_id="rf-1"):
    client = MagicMock()
    client.upload_document.return_value = [{"id": doc_id}]
    return client


@pytest.fixture
def enabled(db, settings):
    settings.SMART_ASSISTANT_INGEST_DATASET_ID = DATASET
    RagflowConfig.objects.create(name="rf", api_endpoint="http://ragflow.local", api_key="k", is_active=True)
    return settings


@pytest.fixture
def admin(db):
    return make_user("ingest-admin", group="Admin", is_staff=True)


@pytest.fixture
def owner(db):
    return make_user("doc-owner")


@pytest.fixture
def other(db):
    return make_user("doc-other")


def published(title="放假通知", content="<p>国庆<b>放假</b>七天</p>"):
    return Announcement.objects.create(title=title, content=content, status=Announcement.STATUS_PUBLISHED)


# ---------------------------------------------------------------- 入库内容


class TestContent:
    def test_html_to_text(self):
        assert html_to_text("<p>第一段</p><p>A &amp; B<br>换行</p>") == "第一段\nA & B\n换行"

    def test_published_announcement(self, db):
        ann = published()
        content = build_announcement(ann.pk)
        assert content.title == "放假通知"
        assert "国庆放假七天" in content.body and "<p>" not in content.body
        assert content.file_name == f"announcement-{ann.pk}.md"
        assert content.render().startswith("# 放假通知")

    def test_draft_and_missing_announcement(self, db):
        draft = Announcement.objects.create(title="草稿", content="x", status=Announcement.STATUS_DRAFT)
        assert build_announcement(draft.pk) is None
        assert build_announcement(99999) is None

    def test_paperless_uses_ocr_text(self, owner):
        binding = make_binding(owner)
        with patch(GET_DOC, return_value={"content": "合同正文 金额 10 万"}) as get_doc:
            content = build_paperless(binding.pk)
        get_doc.assert_called_once_with(101)
        assert "合同正文" in content.body and "合同" in content.body
        assert content.file_name == f"paperless-{binding.pk}.md"

    def test_paperless_not_synced_and_not_ready(self, owner):
        unsynced = make_binding(owner, paperless_id=None, source_id=2)
        assert build_paperless(unsynced.pk) is None
        synced = make_binding(owner, source_id=3, paperless_id=103)
        with patch(GET_DOC, return_value={"content": "  "}), pytest.raises(ContentNotReady):
            build_paperless(synced.pk)

    def test_long_body_truncated(self, db):
        ann = published(content="字" * 250_000)
        rendered = build_announcement(ann.pk).render()
        assert len(rendered) < 201_000 and "已截断" in rendered


# ---------------------------------------------------------------- 同步


class TestSync:
    def test_disabled_without_dataset(self, db):
        ann = published()
        assert sync_source("announcement", ann.pk) == "disabled"
        assert not KnowledgeSource.objects.exists()

    def test_disabled_without_active_config(self, db, settings):
        settings.SMART_ASSISTANT_INGEST_DATASET_ID = DATASET
        assert sync_source("announcement", published().pk) == "disabled"

    def test_first_ingest_uploads_and_parses(self, enabled):
        ann = published()
        client = fake_client()
        with patch.object(sync_module, "make_client", return_value=client):
            assert sync_source("announcement", ann.pk) == "ingested"
        kwargs = client.upload_document.call_args.kwargs
        assert kwargs["dataset_id"] == DATASET and kwargs["file_name"] == f"announcement-{ann.pk}.md"
        assert "国庆放假七天".encode() in kwargs["file_content"]
        client.parse_documents.assert_called_once_with(dataset_id=DATASET, document_ids=["rf-1"])
        record = KnowledgeSource.objects.get(source_type="announcement", source_id=ann.pk)
        assert record.status == "ingested" and record.ragflow_document_id == "rf-1"
        assert record.title == "放假通知" and record.content_hash and record.ingested_at
        client.close.assert_called()

    def test_unchanged_content_skipped(self, enabled):
        ann = published()
        client = fake_client()
        with patch.object(sync_module, "make_client", return_value=client):
            sync_source("announcement", ann.pk)
            assert sync_source("announcement", ann.pk) == "skipped"
        assert client.upload_document.call_count == 1

    def test_changed_content_replaces_document(self, enabled):
        ann = published()
        with patch.object(sync_module, "make_client", return_value=fake_client("rf-1")):
            sync_source("announcement", ann.pk)
        Announcement.objects.filter(pk=ann.pk).update(content="<p>改为放假五天</p>")
        client = fake_client("rf-2")
        with patch.object(sync_module, "make_client", return_value=client):
            assert sync_source("announcement", ann.pk) == "ingested"
        client.delete_document.assert_called_once_with(DATASET, ["rf-1"])
        assert KnowledgeSource.objects.get(source_id=ann.pk).ragflow_document_id == "rf-2"

    def test_old_document_delete_failure_does_not_block(self, enabled):
        ann = published()
        with patch.object(sync_module, "make_client", return_value=fake_client("rf-1")):
            sync_source("announcement", ann.pk)
        Announcement.objects.filter(pk=ann.pk).update(title="新标题")
        client = fake_client("rf-2")
        client.delete_document.side_effect = RuntimeError("gone")
        with patch.object(sync_module, "make_client", return_value=client):
            assert sync_source("announcement", ann.pk) == "ingested"
        assert KnowledgeSource.objects.get(source_id=ann.pk).ragflow_document_id == "rf-2"

    def test_unpublished_or_deleted_is_removed(self, enabled):
        ann = published()
        with patch.object(sync_module, "make_client", return_value=fake_client()):
            sync_source("announcement", ann.pk)
        Announcement.objects.filter(pk=ann.pk).update(status=Announcement.STATUS_DRAFT)
        client = fake_client()
        with patch.object(sync_module, "make_client", return_value=client):
            assert sync_source("announcement", ann.pk) == "removed"
            assert sync_source("announcement", ann.pk) == "noop"
        client.delete_document.assert_called_once_with(DATASET, ["rf-1"])
        record = KnowledgeSource.objects.get(source_id=ann.pk)
        assert record.status == "removed" and record.ragflow_document_id == ""

    def test_never_ingested_draft_is_noop(self, enabled):
        draft = Announcement.objects.create(title="草稿", content="x", status=Announcement.STATUS_DRAFT)
        assert sync_source("announcement", draft.pk) == "noop"
        assert not KnowledgeSource.objects.exists()

    def test_upload_failure_recorded(self, enabled):
        ann = published()
        client = fake_client()
        client.upload_document.side_effect = RuntimeError("secret body should not leak")
        with patch.object(sync_module, "make_client", return_value=client):
            assert sync_source("announcement", ann.pk) == "failed"
            assert sync_source("announcement", ann.pk) == "failed"
        record = KnowledgeSource.objects.get(source_id=ann.pk)
        assert record.status == "failed" and record.attempts == 2
        assert record.last_error == "RuntimeError" and "secret" not in record.last_error

    def test_missing_document_id_is_failure(self, enabled):
        client = fake_client()
        client.upload_document.return_value = {}
        with patch.object(sync_module, "make_client", return_value=client):
            assert sync_source("announcement", published().pk) == "failed"

    def test_paperless_not_ready_stays_pending(self, enabled, owner):
        binding = make_binding(owner)
        with patch(GET_DOC, return_value={"content": ""}):
            assert sync_source("paperless_document", binding.pk) == "pending"
        assert KnowledgeSource.objects.get(source_id=binding.pk).status == "pending"

    def test_paperless_fetch_error_is_failure(self, enabled, owner):
        binding = make_binding(owner)
        with patch(GET_DOC, side_effect=RuntimeError("down")):
            assert sync_source("paperless_document", binding.pk) == "failed"

    def test_unknown_type(self, enabled):
        with pytest.raises(ValueError):
            sync_source("book", 1)


# ---------------------------------------------------------------- 触发


class TestTriggers:
    def test_no_enqueue_when_not_configured(self, admin, django_capture_on_commit_callbacks):
        with patch(TASK_DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
            published()
        delay.assert_not_called()

    def test_publish_create_update_delete_enqueue(self, enabled, django_capture_on_commit_callbacks):
        with patch(TASK_DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
            ann = published()
        delay.assert_called_once_with("announcement", ann.pk)
        KnowledgeSource.objects.create(source_type="announcement", source_id=ann.pk, status="ingested")
        with patch(TASK_DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
            ann.title = "改了"
            ann.save()
            ann.delete()
        assert delay.call_count == 2

    def test_draft_without_record_not_enqueued(self, enabled, django_capture_on_commit_callbacks):
        with patch(TASK_DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
            Announcement.objects.create(title="草稿", content="x", status=Announcement.STATUS_DRAFT)
        delay.assert_not_called()

    def test_publish_endpoint_enqueues(self, enabled, admin, django_capture_on_commit_callbacks):
        draft = Announcement.objects.create(title="草稿", content="x", status=Announcement.STATUS_DRAFT)
        with patch(TASK_DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
            response = client_for(admin).post(f"{ANN_URL}{draft.pk}/publish/")
        assert response.status_code == 200
        delay.assert_called_once_with("announcement", draft.pk)

    def test_binding_signals(self, enabled, owner, django_capture_on_commit_callbacks):
        with patch(TASK_DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
            binding = make_binding(owner, paperless_id=None)
        delay.assert_not_called()
        with patch(TASK_DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
            binding.paperless_id = 55
            binding.save()
        delay.assert_called_once_with("paperless_document", binding.pk)
        binding_id = binding.pk
        KnowledgeSource.objects.create(source_type="paperless_document", source_id=binding_id, status="ingested")
        with patch(TASK_DELAY) as delay, django_capture_on_commit_callbacks(execute=True):
            binding.delete()
        delay.assert_called_once_with("paperless_document", binding_id)

    def test_queue_failure_is_swallowed(self, enabled, django_capture_on_commit_callbacks):
        with patch(TASK_DELAY, side_effect=ConnectionError("broker down")), django_capture_on_commit_callbacks(
            execute=True
        ):
            published()  # 不抛异常，交给对账兜底


# ---------------------------------------------------------------- 对账


class TestReconcile:
    def test_disabled(self, db):
        assert reconcile() == {"disabled": True}

    def test_candidates_order_and_rules(self, enabled, owner):
        now = timezone.now()
        fresh = published("新公告")
        changed = published("改过的")
        ok = published("没变的")
        failing = published("还能重试")
        dead = published("失败太多")
        gone_record = KnowledgeSource.objects.create(source_type="announcement", source_id=99999, status="ingested")
        KnowledgeSource.objects.create(
            source_type="announcement", source_id=changed.pk, status="ingested", ingested_at=now - timedelta(days=1)
        )
        KnowledgeSource.objects.create(
            source_type="announcement", source_id=ok.pk, status="ingested", ingested_at=now + timedelta(minutes=1)
        )
        KnowledgeSource.objects.create(source_type="announcement", source_id=failing.pk, status="failed", attempts=1)
        KnowledgeSource.objects.create(
            source_type="announcement", source_id=dead.pk, status="failed", attempts=MAX_ATTEMPTS
        )
        binding = make_binding(owner)

        candidates = reconcile_candidates()
        assert candidates[0] == ("announcement", gone_record.source_id)  # 移除优先
        assert ("announcement", fresh.pk) in candidates and ("announcement", changed.pk) in candidates
        assert ("paperless_document", binding.pk) in candidates
        assert ("announcement", failing.pk) in candidates
        assert ("announcement", ok.pk) not in candidates
        assert ("announcement", dead.pk) not in candidates
        assert len(reconcile_candidates(limit=2)) == 2

    def test_reconcile_runs_sync(self, enabled):
        published()
        with patch.object(sync_module, "make_client", return_value=fake_client()):
            result = reconcile()
        assert result == {"disabled": False, "ingested": 1}
        assert reconcile_candidates() == []

    def test_task_wrappers(self, enabled):
        from smart_assistant.tasks import reconcile_knowledge_sources, sync_knowledge_source

        ann = published()
        with patch.object(sync_module, "make_client", return_value=fake_client()):
            assert sync_knowledge_source("announcement", str(ann.pk)) == {"outcome": "ingested"}
            assert reconcile_knowledge_sources() == {"disabled": False}


# ---------------------------------------------------------------- 检索过滤


def ingest_chunk(doc_id, content, similarity=0.9):
    return {"content": content, "document_id": doc_id, "similarity": similarity, "_ingest": True}


class TestAcl:
    @pytest.fixture
    def indexed(self, owner):
        ann = published("放假通知")
        binding = make_binding(owner, title="采购合同")
        KnowledgeSource.objects.create(
            source_type="announcement", source_id=ann.pk, status="ingested", ragflow_document_id="rf-ann", title="放假通知"
        )
        KnowledgeSource.objects.create(
            source_type="paperless_document",
            source_id=binding.pk,
            status="ingested",
            ragflow_document_id="rf-doc",
            title="采购合同",
        )
        return ann, binding

    def chunks(self):
        return [
            {"content": "手动知识库", "similarity": 0.5},
            ingest_chunk("rf-ann", "公告内容"),
            ingest_chunk("rf-doc", "合同内容"),
            ingest_chunk("rf-unknown", "来历不明"),
        ]

    def test_owner_sees_own_document(self, indexed, owner):
        kept = [c["content"] for c in filter_chunks(owner, self.chunks())]
        assert kept == ["手动知识库", "公告内容", "合同内容"]

    def test_other_user_cannot_see_document(self, indexed, other):
        kept = filter_chunks(other, self.chunks())
        assert [c["content"] for c in kept] == ["手动知识库", "公告内容"]
        assert kept[1]["_source"] == "公告：放假通知" and kept[1]["document_name"] == "放假通知"

    def test_staff_sees_all_documents(self, indexed):
        staff = make_user("staffer", is_staff=True)
        assert len(filter_chunks(staff, self.chunks())) == 3

    def test_unpublished_or_deleted_hidden_immediately(self, indexed, owner):
        ann, binding = indexed
        Announcement.objects.filter(pk=ann.pk).update(status=Announcement.STATUS_DRAFT)
        assert [c["content"] for c in filter_chunks(owner, self.chunks())] == ["手动知识库", "合同内容"]
        binding.delete()
        assert [c["content"] for c in filter_chunks(owner, self.chunks())] == ["手动知识库"]

    def test_record_not_ingested_hidden(self, indexed, owner):
        KnowledgeSource.objects.filter(ragflow_document_id="rf-ann").update(status="removed")
        assert "公告内容" not in [c["content"] for c in filter_chunks(owner, self.chunks())]

    def test_anonymous_gets_only_public(self, indexed):
        assert [c["content"] for c in filter_chunks(None, self.chunks())] == ["手动知识库"]

    def test_no_ingest_chunks_untouched(self, db):
        chunks = [{"content": "a"}, {"content": "b"}]
        assert filter_chunks(None, chunks) == chunks


class TestRouterAndTool:
    def patch_retrieval(self, by_dataset):
        client = MagicMock()
        client.retrieval.side_effect = lambda dataset_ids, question, top_k: [dict(c) for c in by_dataset[dataset_ids[0]]]
        return patch("smart_assistant.agent.rag_router.RagflowClient", return_value=client), client

    def test_router_adds_ingest_dataset_and_filters(self, enabled, owner, other):
        from smart_assistant.models import KnowledgeDataset

        KnowledgeDataset.objects.create(name="公共库", ragflow_dataset_id="ds-public", is_active=True)
        binding = make_binding(owner)
        KnowledgeSource.objects.create(
            source_type="paperless_document", source_id=binding.pk, status="ingested", ragflow_document_id="rf-doc"
        )
        by_dataset = {
            "ds-public": [{"content": "公共", "similarity": 0.3}],
            DATASET: [{"content": "私有合同", "document_id": "rf-doc", "similarity": 0.8}],
        }
        patcher, client = self.patch_retrieval(by_dataset)
        with patcher:
            mine = RAGRouter().search_multi("合同", top_k=5, user=owner)
            theirs = RAGRouter().search_multi("合同", top_k=5, user=other)
        assert [c["content"] for c in mine] == ["私有合同", "公共"]  # 按相似度排序
        assert [c["content"] for c in theirs] == ["公共"]
        top_ks = {call.kwargs["dataset_ids"][0]: call.kwargs["top_k"] for call in client.retrieval.call_args_list}
        assert top_ks[DATASET] == 15 and top_ks["ds-public"] == 5

    def test_ingest_dataset_registered_as_knowledge_dataset_still_filtered(self, enabled, other):
        from smart_assistant.models import KnowledgeDataset

        KnowledgeDataset.objects.create(name="入库", ragflow_dataset_id=DATASET, is_active=True)
        patcher, client = self.patch_retrieval({DATASET: [{"content": "私有", "document_id": "rf-x"}]})
        with patcher:
            assert RAGRouter().search_multi("x", user=other) == []
        assert client.retrieval.call_count == 1

    def test_router_unchanged_when_disabled(self, db):
        router = RAGRouter()
        assert router.ingest_dataset() is None

    def test_tool_passes_context_user(self, other):
        with patch("smart_assistant.agent.rag_router.get_rag_router") as get_router:
            get_router.return_value.search_multi.return_value = []
            RAGTool().execute(query="合同", context={"user": other})
        assert get_router.return_value.search_multi.call_args.kwargs["user"] == other


# ---------------------------------------------------------------- 管理端


class TestAdminApi:
    def test_requires_assistant_admin(self, owner):
        staff_only = make_user("staff-only", is_staff=True)
        for user in (owner, staff_only):
            assert client_for(user).get(f"{API}/summary/").status_code == 403

    def test_summary(self, enabled, admin):
        KnowledgeSource.objects.create(source_type="announcement", source_id=1, status="ingested")
        KnowledgeSource.objects.create(
            source_type="paperless_document", source_id=2, status="failed", attempts=3, last_error="RuntimeError"
        )
        data = client_for(admin).get(f"{API}/summary/").json()
        assert data["enabled"] is True and data["dataset_configured"] is True
        assert data["counts"]["announcement"]["ingested"] == 1
        assert data["counts"]["paperless_document"]["failed"] == 1
        assert data["failures"][0]["source_type_display"] == "文档库" and data["failures"][0]["attempts"] == 3

    def test_summary_when_disabled(self, admin):
        data = client_for(admin).get(f"{API}/summary/").json()
        assert data["enabled"] is False and data["dataset_configured"] is False

    def test_reconcile_and_retry(self, enabled, admin):
        record = KnowledgeSource.objects.create(
            source_type="announcement", source_id=7, status="failed", attempts=MAX_ATTEMPTS
        )
        client = client_for(admin)
        with patch("smart_assistant.tasks.reconcile_knowledge_sources.delay") as delay:
            assert client.post(f"{API}/reconcile/").status_code == 202
        delay.assert_called_once()
        with patch(TASK_DELAY) as delay:
            response = client.post(f"{API}/{record.pk}/retry/")
        assert response.status_code == 202
        delay.assert_called_once_with("announcement", 7)
        record.refresh_from_db()
        assert record.attempts == 0

    def test_actions_rejected_when_disabled_or_queue_down(self, admin, enabled):
        record = KnowledgeSource.objects.create(source_type="announcement", source_id=7, status="failed")
        client = client_for(admin)
        with patch(TASK_DELAY, side_effect=ConnectionError()):
            assert client.post(f"{API}/{record.pk}/retry/").status_code == 503
        with patch("smart_assistant.tasks.reconcile_knowledge_sources.delay", side_effect=ConnectionError()):
            assert client.post(f"{API}/reconcile/").status_code == 503
        enabled.SMART_ASSISTANT_INGEST_DATASET_ID = ""
        assert client.post(f"{API}/reconcile/").status_code == 409
        assert client.post(f"{API}/{record.pk}/retry/").status_code == 409


class TestContextPropagation:
    """scope 分支也把 ToolContext 传给工具（原生路径早已如此），knowledge_qa 才能识别用户。"""

    def test_tool_chain_scope_branch_passes_context(self, other):
        from smart_assistant.agent.tool_chain_executor import ToolChainExecutor

        tool = MagicMock(supports_scope_filter=True)
        tool.execute.return_value = {"found": False}
        context = MagicMock(scope="all", user=other)
        executor = ToolChainExecutor.__new__(ToolChainExecutor)
        with patch("smart_assistant.agent.tool_chain_executor.apply_post_execute_hooks", side_effect=lambda t, o, c: o):
            executor._call_tool(tool, {"query": "合同"}, context)
        assert tool.execute.call_args.kwargs["context"] is context
