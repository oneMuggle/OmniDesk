import pytest
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.utils import timezone

from memos.models import Memo
from smart_assistant.models import AgentWriteLog
from smart_assistant.tools.memo_write_tools import MemoCreateTool
from smart_assistant.tools.memo_write_tools_v2 import MemoDeleteTool, MemoUpdateTool
from smart_assistant.tools.tool_context import ToolContext


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="stage7-user", password="x")


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user(username="stage7-other", password="x")


@pytest.mark.django_db
class TestAgentWriteLogModelAndContext:
    def test_context_carries_write_provenance_without_breaking_old_callers(self, user):
        context = ToolContext(user=user, session_id="s-1", task_id="t-1", model_name="model-x")
        assert context.session_id == "s-1"
        assert context.task_id == "t-1"
        assert context.model_name == "model-x"

    def test_memo_queryset_excludes_soft_deleted_rows(self, user):
        deleted = Memo.objects.create(user=user, title="deleted")
        deleted.is_deleted = True
        deleted.deleted_at = timezone.now()
        deleted.save(update_fields=["is_deleted", "deleted_at"])
        assert not Memo.objects.filter(pk=deleted.pk).exists()
        assert Memo.all_objects.filter(pk=deleted.pk).exists()


@pytest.mark.django_db
class TestMemoToolWriteAudit:
    def test_create_confirmed_writes_audit_atomically(self, user):
        with patch("smart_assistant.tools.memo_write_tools.extract_create_params") as extract:
            from smart_assistant.extractors.memo_extractor import CreateParams
            extract.return_value = CreateParams("标题", "内容", None)
            result = MemoCreateTool().execute(
                query="记一条", context={"confirmed": True, "user": user, "session_id": "s1", "tool_name": "memo_create"}
            )
        assert result["found"]
        log = AgentWriteLog.objects.get()
        assert log.operation == "create"
        assert log.target_model == "memos.Memo"
        assert log.target_pk == str(result["result"]["memo_id"])
        assert log.before is None
        assert log.after["title"] == "标题"
        assert log.session_id == "s1"

    def test_create_rejects_task_owned_by_other_user_without_persisting(self, user, other_user):
        from smart_assistant.models import AgentTask
        task = AgentTask.objects.create(task_id=uuid4(), user=other_user, objective="other", task_packet={})
        with patch("smart_assistant.tools.memo_write_tools.extract_create_params") as extract:
            from smart_assistant.extractors.memo_extractor import CreateParams
            extract.return_value = CreateParams("标题", "内容", None)
            result = MemoCreateTool().execute(query="记", context={"confirmed": True, "user": user, "task_id": task.task_id})
        assert result["found"] is False
        assert Memo.all_objects.filter(user=user, title="标题").count() == 0
        assert not AgentWriteLog.objects.filter(user=user).exists()

        memo = Memo.objects.create(user=user, title="旧", content="原文")
        with patch("smart_assistant.tools.memo_write_tools_v2.extract_update_params") as extract:
            from smart_assistant.extractors.memo_update_extractor import UpdateParams
            extract.return_value = UpdateParams("旧", "新", "新文", None)
            result = MemoUpdateTool().execute(
                query="改", context={"confirmed": True, "user": user, "draft": {"memo_id": memo.pk, "target_title": "旧", "new_title": "新", "new_content": "新文"}}
            )
        assert result["found"]
        update_log = AgentWriteLog.objects.get(operation="update")
        assert update_log.before["title"] == "旧"
        assert update_log.after["title"] == "新"

        with patch("smart_assistant.tools.memo_write_tools_v2.extract_delete_params") as extract:
            from smart_assistant.extractors.memo_delete_extractor import DeleteParams
            extract.return_value = DeleteParams("新")
            result = MemoDeleteTool().execute(
                query="删", context={"confirmed": True, "user": user, "draft": {"memo_id": memo.pk, "target_title": "新"}}
            )
        assert result["found"]
        delete_log = AgentWriteLog.objects.get(operation="delete")
        assert delete_log.before["is_deleted"] is False
        assert delete_log.after["is_deleted"] is True
        assert Memo.all_objects.get(pk=memo.pk).is_deleted

    def test_update_rejects_task_owned_by_other_user_without_persisting(self, user, other_user):
        from smart_assistant.models import AgentTask
        task = AgentTask.objects.create(task_id=uuid4(), user=other_user, objective="other", task_packet={})
        memo = Memo.objects.create(user=user, title="旧", content="原文")
        with patch("smart_assistant.tools.memo_write_tools_v2.extract_update_params") as extract:
            from smart_assistant.extractors.memo_update_extractor import UpdateParams
            extract.return_value = UpdateParams("旧", "新", None, None)
            result = MemoUpdateTool().execute(
                query="改", context={"confirmed": True, "user": user, "task_id": task.task_id,
                "draft": {"memo_id": memo.pk, "target_title": "旧"}}
            )
        assert result["found"] is False
        memo.refresh_from_db()
        assert memo.title == "旧"
        assert not AgentWriteLog.objects.filter(user=user).exists()


@pytest.mark.django_db
class TestWriteLogAPI:
    def setup_method(self):
        self.client = APIClient()

    def test_list_is_owned_and_revert_requires_current_after(self, user, other_user):
        memo = Memo.objects.create(user=user, title="new")
        log = AgentWriteLog.objects.create(
            user=user, session_id="s", tool_name="memo_update", target_model="memos.Memo",
            target_pk=str(memo.pk), operation="update", before={"title": "old"}, after={"title": "new"},
        )
        other_log = AgentWriteLog.objects.create(
            user=other_user, tool_name="memo_update", target_model="memos.Memo", target_pk="1",
            operation="update", before={}, after={},
        )
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/smart-assistant/write-logs/")
        assert response.status_code == 200
        ids = {item["id"] for item in response.data["results"]}
        assert log.pk in ids and other_log.pk not in ids

        response = self.client.post(f"/api/smart-assistant/write-logs/{log.pk}/revert/")
        assert response.status_code == 200
        memo.refresh_from_db()
        assert memo.title == "old"
        revert = AgentWriteLog.objects.get(revert_of=log)
        assert revert.operation == "update"
        assert revert.before["title"] == "new"
        assert revert.after["title"] == "old"

    def test_list_filters_by_task_id(self, user):
        from smart_assistant.models import AgentTask
        task = AgentTask.objects.create(task_id=uuid4(), user=user, objective="t", task_packet={})
        other_task = AgentTask.objects.create(task_id=uuid4(), user=user, objective="o", task_packet={})
        first = AgentWriteLog.objects.create(user=user, task=task, tool_name="memo_create", target_model="memos.Memo", target_pk="1", operation="create")
        AgentWriteLog.objects.create(user=user, task=other_task, tool_name="memo_create", target_model="memos.Memo", target_pk="2", operation="create")
        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/smart-assistant/write-logs/?task_id={task.task_id}")
        assert [item["id"] for item in response.data["results"]] == [first.pk]

        memo = Memo.objects.create(user=user, title="new", content="body")
        log = AgentWriteLog.objects.create(
            user=user,
            tool_name="memo_create",
            target_model="memos.Memo",
            target_pk=str(memo.pk),
            operation="create",
            before=None,
            after={
                "title": "new",
                "content": "body",
                "reminder_time": None,
                "is_deleted": False,
                "deleted_at": None,
            },
        )
        self.client.force_authenticate(user=user)

        response = self.client.post(f"/api/smart-assistant/write-logs/{log.pk}/revert/")

        assert response.status_code == 200
        memo.refresh_from_db()
        assert memo.is_deleted is True
        assert memo.deleted_at is not None

    def test_revert_conflict_is_409_and_delete_is_not_reversible(self, user):
        memo = Memo.objects.create(user=user, title="changed")
        log = AgentWriteLog.objects.create(
            user=user, tool_name="memo_update", target_model="memos.Memo", target_pk=str(memo.pk),
            operation="update", before={"title": "old"}, after={"title": "new"},
        )
        self.client.force_authenticate(user=user)
        response = self.client.post(f"/api/smart-assistant/write-logs/{log.pk}/revert/")
        assert response.status_code == 409
        assert AgentWriteLog.objects.filter(revert_of=log).count() == 0

        delete_log = AgentWriteLog.objects.create(
            user=user, tool_name="memo_delete", target_model="memos.Memo", target_pk=str(memo.pk),
            operation="delete", before={"is_deleted": False}, after={"is_deleted": True},
        )
        response = self.client.post(f"/api/smart-assistant/write-logs/{delete_log.pk}/revert/")
        assert response.status_code == 409
