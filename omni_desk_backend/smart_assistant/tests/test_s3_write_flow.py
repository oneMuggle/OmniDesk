"""S3-1 写操作统一流程：确认预览、确认 / 取消接口、通用撤销、参数解析。"""

from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from memos.models import Memo
from smart_assistant.cache import get_confirmation_draft, public_confirmation_draft, set_confirmation_draft
from smart_assistant.models import AgentWriteLog
from smart_assistant.scope import resolve_scope
from smart_assistant.tools.notification_write_tools import NotificationMarkReadTool
from smart_assistant.writes.preview import build_preview, change, public_preview
from smart_assistant.writes.revert import REVERT_HANDLERS, RevertConflict

API = "/api/smart-assistant"


@pytest.fixture(autouse=True)
def _run_tools_inline(settings):
    settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = False


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="s3-flow", password="x")


@pytest.fixture
def other(db):
    return get_user_model().objects.create_user(username="s3-flow-other", password="x")


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def stash(user, tool_name="notification_mark_read", fields=None, preview=None):
    token = uuid4().hex
    set_confirmation_draft(
        token,
        {
            "tool_name": tool_name,
            "user_query": "原话",
            "context_sig": f"u{user.pk}_s{resolve_scope(user).value}",
            "draft": {"summary": "原话摘要", "fields": fields or {"notification_ids": [1]}, "preview": preview},
        },
    )
    return token


# ---------------------------------------------------------------------------
# 确认预览
# ---------------------------------------------------------------------------


class TestPreview:
    def test_public_preview_keeps_whitelist_and_truncates(self):
        preview = build_preview(
            action="更新状态",
            target_type="合规问题",
            target_label="很长" * 200,
            changes=[change(f"f{i}", f"字段{i}", "a", "b") for i in range(20)],
            affected_count=3,
            items=[f"条目{i}" for i in range(9)],
        )
        preview["secret_extra"] = "不应公开"
        preview["target"]["raw"] = "不应公开"
        public = public_preview(preview)
        assert "secret_extra" not in public and "raw" not in public["target"]
        assert len(public["target"]["label"]) <= 120
        assert len(public["changes"]) == 10 and len(public["items"]) == 5
        assert public["affected_count"] == 3

    def test_public_preview_masks_secrets_and_bad_values(self):
        public = public_preview(
            {
                "action": "x",
                "target": {"type": "t", "label": "password=hunter2"},
                "risk": "root",
                "affected_count": "abc",
            }
        )
        assert "hunter2" not in public["target"]["label"]
        assert public["risk"] == "write" and public["affected_count"] == 0
        assert public_preview("not a dict") is None

    def test_confirmation_draft_summary_comes_from_preview_not_raw_summary(self):
        preview = build_preview(action="预约会议室", target_type="会议室预约", target_label="三楼 · 10-08 14:00–15:00")
        public = public_confirmation_draft({"summary": "用户原话 QUERY_SECRET", "fields": {}, "preview": preview}, "x")
        assert public["summary"] == "待确认：预约会议室 · 三楼 · 10-08 14:00–15:00"
        assert public["preview"]["action"] == "预约会议室"
        assert "QUERY_SECRET" not in str(public)

    def test_confirmation_draft_without_preview_is_unchanged(self):
        public = public_confirmation_draft({"summary": "原话", "fields": {"operation": "x"}}, "memo_create")
        assert public == {"summary": "请确认工具操作", "fields": {"operation": "x"}}


# ---------------------------------------------------------------------------
# 确认 / 取消接口
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConfirmationEndpoints:
    def test_expired_token_is_410(self, user):
        for action in ("approve", "reject"):
            response = client_for(user).post(f"{API}/confirmations/{uuid4().hex}/{action}/")
            assert response.status_code == 410 and response.data["code"] == "confirmation_expired"

    def test_reject_consumes_token_and_repeat_is_409(self, user):
        token = stash(user)
        response = client_for(user).post(f"{API}/confirmations/{token}/reject/")
        assert response.status_code == 200 and response.data["rejected"] is True
        assert get_confirmation_draft(token) is None
        again = client_for(user).post(f"{API}/confirmations/{token}/reject/")
        assert again.status_code == 409 and again.data["code"] == "confirmation_already_rejected"
        approve = client_for(user).post(f"{API}/confirmations/{token}/approve/")
        assert approve.status_code == 409 and approve.data["code"] == "confirmation_already_rejected"

    def test_other_user_cannot_reject_and_does_not_learn_outcome(self, user, other):
        token = stash(user)
        assert client_for(other).post(f"{API}/confirmations/{token}/reject/").status_code == 403
        assert get_confirmation_draft(token) is not None  # 他人的请求不消费 token
        client_for(user).post(f"{API}/confirmations/{token}/reject/")
        # 消费后，其他人只会看到"不存在"
        assert client_for(other).post(f"{API}/confirmations/{token}/approve/").status_code == 410

    def test_business_failure_is_400_and_conflict_is_409(self, user):
        token = stash(user, fields={"notification_ids": [999999]})
        response = client_for(user).post(f"{API}/confirmations/{token}/approve/")
        # 通知不存在（或已读）→ state_conflict → 409
        assert response.status_code == 409 and response.data["code"] == "state_conflict"

        token = stash(user, fields={"notification_ids": []})
        with patch.object(NotificationMarkReadTool, "confirm", return_value={"found": False, "message": "x"}):
            response = client_for(user).post(f"{API}/confirmations/{token}/approve/")
        assert response.status_code == 400 and response.data["code"] == "write_failed"

    def test_generic_failure_maps_to_400(self, user):
        token = stash(user)
        with patch.object(
            NotificationMarkReadTool, "confirm", return_value={"found": False, "message": "出错了", "error_code": "x"}
        ):
            response = client_for(user).post(f"{API}/confirmations/{token}/approve/")
        assert response.status_code == 400 and response.data == {
            "detail": "出错了",
            "code": "x",
            "tool_used": "notification_mark_read",
        }

    def test_typing_confirm_in_chat_does_not_execute(self, user):
        """只有凭 token 调用确认接口才会执行；对话里说"确认"只是一条普通消息。"""
        token = stash(user)
        with (
            patch("smart_assistant.views.chat_sync.AgentOrchestrator") as orchestrator,
            patch.object(NotificationMarkReadTool, "confirm") as confirm,
        ):
            orchestrator.return_value.process.return_value = {
                "answer": "好的",
                "intent": "general",
                "tool_used": None,
                "tool_result": {},
                "sources": None,
                "error": False,
            }
            for text in ("确认", "同意执行", "yes"):
                response = client_for(user).post(f"{API}/chat/", {"query": text}, format="json")
                assert response.status_code == 200
        confirm.assert_not_called()
        assert get_confirmation_draft(token) is not None


# ---------------------------------------------------------------------------
# 通用撤销
# ---------------------------------------------------------------------------


def _log(user, **overrides):
    values = {
        "user": user,
        "tool_name": "t",
        "target_model": "memos.Memo",
        "target_pk": "1",
        "operation": "update",
        "before": {},
        "after": {},
    }
    values.update(overrides)
    return AgentWriteLog.objects.create(**values)


@pytest.mark.django_db
class TestGenericRevert:
    def test_unregistered_model_is_409(self, user):
        log = _log(user, target_model="unknown.Model")
        response = client_for(user).post(f"{API}/write-logs/{log.pk}/revert/")
        assert response.status_code == 409 and "暂不支持" in response.data["detail"]

    def test_revert_operation_itself_is_not_revertible_again_by_type(self, user):
        log = _log(user, operation="revert")
        assert client_for(user).post(f"{API}/write-logs/{log.pk}/revert/").status_code == 409

    def test_other_users_log_is_404(self, user, other):
        log = _log(other)
        assert client_for(user).post(f"{API}/write-logs/{log.pk}/revert/").status_code == 404

    def test_handler_failure_rolls_back_partial_changes(self, user):
        memo = Memo.objects.create(user=user, title="原标题", content="c")
        log = _log(user, target_pk=str(memo.pk))

        class HalfwayHandler:
            def revert(self, log, user):
                Memo.objects.filter(pk=memo.pk).update(title="改了一半")
                raise RevertConflict("中途失败")

        with patch("smart_assistant.views.write_logs.get_revert_handler", return_value=HalfwayHandler()):
            response = client_for(user).post(f"{API}/write-logs/{log.pk}/revert/")
        assert response.status_code == 409
        memo.refresh_from_db()
        assert memo.title == "原标题"
        log.refresh_from_db()
        assert log.reverted_at is None

    def test_every_s3_target_model_has_a_handler(self):
        assert set(REVERT_HANDLERS) >= {
            "memos.Memo",
            "notifications.Notification",
            "meeting_rooms.MeetingRoomBooking",
            "compliance.ComplianceIssue",
        }


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------


class TestParamResolution:
    def test_structured_params_are_preferred(self):
        tool = NotificationMarkReadTool()
        with patch("smart_assistant.extractors.write_fields_extractor.extract_fields") as extract:
            params = tool.resolve_params("q", {"params": {"query": "q", "keyword": "会议"}})
        extract.assert_not_called()
        assert params == {"notification_ids": None, "keyword": "会议", "all_unread": None}

    def test_falls_back_to_llm_extraction(self):
        tool = NotificationMarkReadTool()
        with patch(
            "smart_assistant.extractors.write_fields_extractor.call_extractor_llm",
            return_value='好的：{"keyword": "报销", "all_unread": false, "extra": 1}',
        ):
            params = tool.resolve_params("把报销通知标为已读", {"params": {"query": "q"}})
        assert params == {"notification_ids": None, "keyword": "报销", "all_unread": False}

    @pytest.mark.parametrize("raw", [None, "", "没有 JSON", "{bad json}", "[1, 2]"])
    def test_extraction_failure_returns_none(self, raw):
        from smart_assistant.extractors.write_fields_extractor import extract_fields

        with patch("smart_assistant.extractors.write_fields_extractor.call_extractor_llm", return_value=raw):
            assert extract_fields("q", task="t", fields={"a": "b"}) is None
        assert extract_fields("   ", task="t", fields={"a": "b"}) is None

    @pytest.mark.django_db
    def test_unparseable_request_fails_gracefully(self, user):
        tool = NotificationMarkReadTool()
        with patch("smart_assistant.extractors.write_fields_extractor.call_extractor_llm", return_value=None):
            result = tool.execute("随便说说", context={"dry_run": True, "user": user})
        assert result["found"] is False and "没能理解" in result["message"]

    @pytest.mark.django_db
    def test_missing_mode_and_anonymous(self, user):
        tool = NotificationMarkReadTool()
        assert tool.execute("q", context={"user": user})["found"] is False
        assert tool.execute("q", context={"dry_run": True, "user": None})["found"] is False
        result = tool.execute("q", context={"confirmed": True, "user": user, "draft": {}})
        assert result["error_code"] == "stale_confirmation"
