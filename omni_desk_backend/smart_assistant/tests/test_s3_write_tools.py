"""S3-1 四个写工具的完整流程测试。

每个工具覆盖：批准、拒绝、重复提交（409）、取消后再确认（409）、撤销、撤销冲突（409）、
执行时冲突（409）、越权。流程走真实接口：dry_run 生成草稿 → approve / reject → revert。
"""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from compliance.models import ComplianceIssue
from meeting_rooms.models import MeetingRoom, MeetingRoomBooking, MeetingRoomMaintenance
from notifications.models import Notification
from projects.models import Project
from smart_assistant.cache import set_confirmation_draft
from smart_assistant.models import AgentWriteLog
from smart_assistant.scope import resolve_scope
from smart_assistant.tools.registry import ToolRegistry

API = "/api/smart-assistant"


@pytest.fixture(autouse=True)
def _run_tools_inline(settings):
    """测试库是 sqlite 内存库，工具线程看不到测试事务；关闭超时线程，直接在当前线程执行。"""
    settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = False


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def make_user(username, **extra):
    return get_user_model().objects.create_user(username=username, password="x", **extra)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def dry_run(tool_name, user, params, query="用户原话-不应出现在预览里"):
    tool = ToolRegistry.get_tool_for_user(tool_name, user)
    assert tool is not None, tool_name
    return tool.execute(query, context={"dry_run": True, "user": user, "params": {"query": query, **params}})


def stage(tool_name, user, params, query="用户原话-不应出现在预览里"):
    """dry_run 并把草稿存入缓存；返回 (token, draft)。"""
    result = dry_run(tool_name, user, params, query)
    assert result["found"], result
    token = uuid4().hex
    set_confirmation_draft(
        token,
        {
            "tool_name": tool_name,
            "user_query": query,
            "context_sig": f"u{user.pk}_s{resolve_scope(user).value}",
            "draft": result["draft"],
        },
    )
    return token, result["draft"]


def approve(user, token):
    return client_for(user).post(f"{API}/confirmations/{token}/approve/")


def reject(user, token):
    return client_for(user).post(f"{API}/confirmations/{token}/reject/")


def revert(user, log_id):
    return client_for(user).post(f"{API}/write-logs/{log_id}/revert/")


def future(hours=24, minutes=0):
    base = timezone.now().replace(second=0, microsecond=0) + timedelta(hours=hours, minutes=minutes)
    return base


def local_str(dt):
    return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")


# ---------------------------------------------------------------------------
# 通知标记已读
# ---------------------------------------------------------------------------


@pytest.fixture
def notif_user(db):
    return make_user("s3-notif")


@pytest.fixture
def notifications(notif_user):
    rows = [
        Notification.objects.create(user=notif_user, type="system", title=f"会议提醒 {i}", content="c")
        for i in range(3)
    ]
    rows.append(Notification.objects.create(user=notif_user, type="system", title="报销审批", content="c"))
    return rows


@pytest.mark.django_db
class TestNotificationMarkRead:
    def test_preview_is_built_from_records_not_user_query(self, notif_user, notifications):
        token, draft = stage("notification_mark_read", notif_user, {"keyword": "会议"})
        preview = draft["preview"]
        assert preview["affected_count"] == 3
        assert preview["permission_source"] == "本人的通知"
        assert preview["changes"][0]["before"] == "未读" and preview["changes"][0]["after"] == "已读"
        assert "用户原话" not in str(preview)

    def test_approve_marks_read_and_revert_restores(self, notif_user, notifications):
        token, _ = stage("notification_mark_read", notif_user, {"keyword": "会议"})
        response = approve(notif_user, token)
        assert response.status_code == 200, response.data
        assert response.data["reversible"] is True
        log_id = response.data["write_log_id"]
        assert Notification.objects.filter(user=notif_user, is_read=True).count() == 3
        assert Notification.objects.get(title="报销审批").is_read is False

        response = revert(notif_user, log_id)
        assert response.status_code == 200, response.data
        assert Notification.objects.filter(user=notif_user, is_read=True).count() == 0

    def test_revert_skips_notifications_changed_afterwards(self, notif_user, notifications):
        token, _ = stage("notification_mark_read", notif_user, {"all_unread": True})
        log_id = approve(notif_user, token).data["write_log_id"]
        # 其中一条之后被重新处理（read_at 变化）→ 只恢复其余 3 条
        changed = notifications[0]
        Notification.objects.filter(pk=changed.pk).update(read_at=timezone.now() + timedelta(minutes=5))
        assert revert(notif_user, log_id).status_code == 200
        assert list(Notification.objects.filter(user=notif_user, is_read=True).values_list("pk", flat=True)) == [
            changed.pk
        ]

    def test_revert_conflict_when_all_changed(self, notif_user, notifications):
        token, _ = stage("notification_mark_read", notif_user, {"keyword": "报销"})
        log_id = approve(notif_user, token).data["write_log_id"]
        Notification.objects.filter(user=notif_user).update(is_read=False, read_at=None)
        response = revert(notif_user, log_id)
        assert response.status_code == 409
        assert AgentWriteLog.objects.filter(revert_of_id=log_id).count() == 0

    def test_reject_then_confirm_is_409_and_nothing_changes(self, notif_user, notifications):
        token, _ = stage("notification_mark_read", notif_user, {"all_unread": True})
        assert reject(notif_user, token).status_code == 200
        assert approve(notif_user, token).status_code == 409
        assert Notification.objects.filter(is_read=True).count() == 0

    def test_duplicate_approve_is_409(self, notif_user, notifications):
        token, _ = stage("notification_mark_read", notif_user, {"all_unread": True})
        assert approve(notif_user, token).status_code == 200
        response = approve(notif_user, token)
        assert response.status_code == 409 and response.data["code"] == "confirmation_already_used"
        assert AgentWriteLog.objects.filter(tool_name="notification_mark_read").count() == 1

    def test_already_read_at_confirm_time_is_409(self, notif_user, notifications):
        token, _ = stage("notification_mark_read", notif_user, {"keyword": "报销"})
        Notification.objects.filter(title="报销审批").update(is_read=True, read_at=timezone.now())
        response = approve(notif_user, token)
        assert response.status_code == 409 and response.data["code"] == "state_conflict"

    def test_other_users_notifications_are_never_touched(self, notif_user, notifications):
        other = make_user("s3-notif-other")
        foreign = Notification.objects.create(user=other, type="system", title="会议提醒 X", content="c")
        result = dry_run("notification_mark_read", notif_user, {"notification_ids": [foreign.pk]})
        assert result["found"] is False
        # 其他用户也不能确认我的草稿
        token, _ = stage("notification_mark_read", notif_user, {"all_unread": True})
        assert approve(other, token).status_code == 403

    def test_batch_limit(self, notif_user):
        Notification.objects.bulk_create(
            [Notification(user=notif_user, type="system", title=f"n{i}", content="c") for i in range(51)]
        )
        result = dry_run("notification_mark_read", notif_user, {"all_unread": True})
        assert result["found"] is False and "最多" in result["message"]

    def test_requires_explicit_target(self, notif_user, notifications):
        result = dry_run("notification_mark_read", notif_user, {"all_unread": False})
        assert result["found"] is False


# ---------------------------------------------------------------------------
# 会议室预约与取消
# ---------------------------------------------------------------------------


@pytest.fixture
def room(db):
    return MeetingRoom.objects.create(name="三楼大会议室", capacity=20)


@pytest.fixture
def booker(db):
    return make_user("s3-booker")


def book_params(room, start, end, title="项目周会"):
    return {"room": room.name, "start_time": local_str(start), "end_time": local_str(end), "title": title}


@pytest.mark.django_db
class TestMeetingRoomBook:
    def test_approve_creates_booking_and_revert_deletes(self, booker, room):
        start = future()
        token, draft = stage("meeting_room_book", booker, book_params(room, start, start + timedelta(hours=1)))
        assert draft["preview"]["target"]["label"].startswith("三楼大会议室")
        response = approve(booker, token)
        assert response.status_code == 200, response.data
        booking = MeetingRoomBooking.objects.get(user=booker)
        assert booking.title == "项目周会"
        assert revert(booker, response.data["write_log_id"]).status_code == 200
        assert not MeetingRoomBooking.objects.filter(pk=booking.pk).exists()

    def test_conflict_at_dry_run(self, booker, room):
        start = future()
        MeetingRoomBooking.objects.create(
            meeting_room=room, user=make_user("s3-x"), start_time=start, end_time=start + timedelta(hours=2), title="占用"
        )
        result = dry_run(
            "meeting_room_book", booker, book_params(room, start + timedelta(minutes=30), start + timedelta(hours=1))
        )
        assert result["found"] is False and result["error_code"] == "booking_conflict"

    def test_conflict_at_confirm_time_is_409(self, booker, room):
        start = future()
        token, _ = stage("meeting_room_book", booker, book_params(room, start, start + timedelta(hours=1)))
        # 确认前别人抢先订了同一时段
        MeetingRoomBooking.objects.create(
            meeting_room=room, user=make_user("s3-y"), start_time=start, end_time=start + timedelta(hours=1), title="抢"
        )
        response = approve(booker, token)
        assert response.status_code == 409 and response.data["code"] == "booking_conflict"
        assert not MeetingRoomBooking.objects.filter(user=booker).exists()
        assert not AgentWriteLog.objects.filter(user=booker).exists()

    def test_maintenance_blocks_booking(self, booker, room):
        start = future()
        MeetingRoomMaintenance.objects.create(
            meeting_room=room, start_time=start, end_time=start + timedelta(hours=3), reason="检修"
        )
        result = dry_run("meeting_room_book", booker, book_params(room, start, start + timedelta(hours=1)))
        assert result["found"] is False and "维护" in result["message"]

    def test_past_time_and_unknown_room_are_rejected(self, booker, room):
        past = timezone.now() - timedelta(hours=2)
        assert dry_run("meeting_room_book", booker, book_params(room, past, past + timedelta(hours=1)))["found"] is False
        params = book_params(room, future(), future(hours=25))
        params["room"] = "不存在的会议室"
        result = dry_run("meeting_room_book", booker, params)
        assert result["found"] is False and "三楼大会议室" in result["message"]

    def test_duplicate_approve_creates_only_one_booking(self, booker, room):
        start = future()
        token, _ = stage("meeting_room_book", booker, book_params(room, start, start + timedelta(hours=1)))
        assert approve(booker, token).status_code == 200
        assert approve(booker, token).status_code == 409
        assert MeetingRoomBooking.objects.filter(user=booker).count() == 1

    def test_reject_then_confirm(self, booker, room):
        start = future()
        token, _ = stage("meeting_room_book", booker, book_params(room, start, start + timedelta(hours=1)))
        assert reject(booker, token).status_code == 200
        assert approve(booker, token).status_code == 409
        assert not MeetingRoomBooking.objects.exists()

    def test_revert_conflict_when_booking_modified(self, booker, room):
        start = future()
        token, _ = stage("meeting_room_book", booker, book_params(room, start, start + timedelta(hours=1)))
        log_id = approve(booker, token).data["write_log_id"]
        booking = MeetingRoomBooking.objects.get(user=booker)
        booking.title = "改过的主题"
        booking.save()
        assert revert(booker, log_id).status_code == 409
        assert MeetingRoomBooking.objects.filter(pk=booking.pk).exists()

    def test_other_user_cannot_approve_or_revert(self, booker, room):
        other = make_user("s3-book-other")
        start = future()
        token, _ = stage("meeting_room_book", booker, book_params(room, start, start + timedelta(hours=1)))
        assert approve(other, token).status_code == 403
        log_id = approve(booker, token).data["write_log_id"]
        assert revert(other, log_id).status_code == 404


@pytest.fixture
def my_booking(booker, room):
    start = future(hours=48)
    return MeetingRoomBooking.objects.create(
        meeting_room=room, user=booker, start_time=start, end_time=start + timedelta(hours=1), title="需求评审"
    )


@pytest.mark.django_db
class TestMeetingRoomCancel:
    def test_approve_cancels_and_revert_recreates(self, booker, my_booking):
        token, draft = stage("meeting_room_cancel", booker, {"keyword": "需求评审"})
        assert draft["preview"]["permission_source"] == "本人的预约"
        response = approve(booker, token)
        assert response.status_code == 200, response.data
        assert not MeetingRoomBooking.objects.filter(pk=my_booking.pk).exists()

        response = revert(booker, response.data["write_log_id"])
        assert response.status_code == 200, response.data
        restored = MeetingRoomBooking.objects.get(user=booker)
        assert restored.title == "需求评审" and restored.start_time == my_booking.start_time
        assert response.data["operation"] == "create"

    def test_revert_conflict_when_slot_taken(self, booker, room, my_booking):
        token, _ = stage("meeting_room_cancel", booker, {"booking_id": my_booking.pk})
        log_id = approve(booker, token).data["write_log_id"]
        MeetingRoomBooking.objects.create(
            meeting_room=room,
            user=make_user("s3-taker"),
            start_time=my_booking.start_time,
            end_time=my_booking.end_time,
            title="抢到了",
        )
        response = revert(booker, log_id)
        assert response.status_code == 409
        assert "无法恢复" in response.data["detail"]
        assert not MeetingRoomBooking.objects.filter(user=booker).exists()

    def test_cannot_cancel_others_booking_even_as_admin(self, room, my_booking):
        admin = make_user("s3-admin", is_staff=True, is_superuser=True)
        result = dry_run("meeting_room_cancel", admin, {"booking_id": my_booking.pk})
        assert result["found"] is False
        assert MeetingRoomBooking.objects.filter(pk=my_booking.pk).exists()

    def test_stale_version_is_409(self, booker, my_booking):
        token, _ = stage("meeting_room_cancel", booker, {"booking_id": my_booking.pk})
        my_booking.title = "改了"
        my_booking.save()
        response = approve(booker, token)
        assert response.status_code == 409 and response.data["code"] == "stale_confirmation"
        assert MeetingRoomBooking.objects.filter(pk=my_booking.pk).exists()

    def test_duplicate_and_reject(self, booker, my_booking):
        token, _ = stage("meeting_room_cancel", booker, {"booking_id": my_booking.pk})
        assert reject(booker, token).status_code == 200
        assert reject(booker, token).status_code == 409
        assert approve(booker, token).status_code == 409
        assert MeetingRoomBooking.objects.filter(pk=my_booking.pk).exists()

    def test_ambiguous_match_lists_candidates(self, booker, room, my_booking):
        start = future(hours=72)
        MeetingRoomBooking.objects.create(
            meeting_room=room, user=booker, start_time=start, end_time=start + timedelta(hours=1), title="需求评审二"
        )
        result = dry_run("meeting_room_cancel", booker, {"keyword": "需求评审"})
        assert result["found"] is False and "多个" in result["message"]

    def test_started_booking_cannot_be_cancelled(self, booker, my_booking):
        token, _ = stage("meeting_room_cancel", booker, {"booking_id": my_booking.pk})
        with patch("smart_assistant.tools.meeting_room_write_tools.timezone.now", return_value=my_booking.start_time):
            response = approve(booker, token)
        assert response.status_code == 409 and response.data["code"] == "state_conflict"


# ---------------------------------------------------------------------------
# 合规问题状态
# ---------------------------------------------------------------------------


@pytest.fixture
def manager(db):
    return make_user("s3-manager")


@pytest.fixture
def issue(manager):
    project = Project.objects.create(name="S3 测试项目", manager=manager)
    return ComplianceIssue.objects.create(project=project, issue_type="其他", description="封面缺少页码", location="第 1 页")


@pytest.mark.django_db
class TestComplianceStatusUpdate:
    def test_manager_approve_and_revert(self, manager, issue):
        token, draft = stage("compliance_issue_update_status", manager, {"keyword": "页码", "new_status": "已解决"})
        preview = draft["preview"]
        assert preview["permission_source"] == "项目负责人"
        assert preview["changes"][0] == {"field": "status", "label": "状态", "before": "待处理", "after": "已解决"}
        response = approve(manager, token)
        assert response.status_code == 200, response.data
        issue.refresh_from_db()
        assert issue.status == "已解决"
        assert revert(manager, response.data["write_log_id"]).status_code == 200
        issue.refresh_from_db()
        assert issue.status == "待处理"

    def test_staff_sees_permission_source(self, issue):
        staff = make_user("s3-staff", is_staff=True)
        _, draft = stage("compliance_issue_update_status", staff, {"issue_id": issue.pk, "new_status": "处理中"})
        assert draft["preview"]["permission_source"] == "管理员（非本人负责的项目）"

    def test_unrelated_user_cannot_see_or_change(self, issue):
        outsider = make_user("s3-outsider")
        result = dry_run("compliance_issue_update_status", outsider, {"issue_id": issue.pk, "new_status": "已解决"})
        assert result["found"] is False

    def test_stale_version_is_409(self, manager, issue):
        token, _ = stage("compliance_issue_update_status", manager, {"issue_id": issue.pk, "new_status": "已解决"})
        ComplianceIssue.objects.filter(pk=issue.pk).update(status="处理中", updated_at=timezone.now() + timedelta(seconds=5))
        response = approve(manager, token)
        assert response.status_code == 409 and response.data["code"] == "stale_confirmation"

    def test_permission_revoked_before_confirm(self, manager, issue):
        token, _ = stage("compliance_issue_update_status", manager, {"issue_id": issue.pk, "new_status": "已解决"})
        Project.objects.filter(pk=issue.project_id).update(manager=None)
        response = approve(manager, token)
        assert response.status_code == 400 and response.data["code"] == "permission_denied"
        issue.refresh_from_db()
        assert issue.status == "待处理"

    def test_revert_conflict_and_revoked_permission(self, manager, issue):
        token, _ = stage("compliance_issue_update_status", manager, {"issue_id": issue.pk, "new_status": "已解决"})
        log_id = approve(manager, token).data["write_log_id"]
        ComplianceIssue.objects.filter(pk=issue.pk).update(status="已忽略")
        response = revert(manager, log_id)
        assert response.status_code == 409 and response.data["current"] == {"status": "已忽略"}

        token, _ = stage("compliance_issue_update_status", manager, {"issue_id": issue.pk, "new_status": "处理中"})
        log_id = approve(manager, token).data["write_log_id"]
        Project.objects.filter(pk=issue.project_id).update(manager=None)
        assert revert(manager, log_id).status_code == 409

    def test_duplicate_reject_and_same_status(self, manager, issue):
        token, _ = stage("compliance_issue_update_status", manager, {"issue_id": issue.pk, "new_status": "已解决"})
        assert approve(manager, token).status_code == 200
        assert approve(manager, token).status_code == 409
        result = dry_run("compliance_issue_update_status", manager, {"issue_id": issue.pk, "new_status": "已解决"})
        assert result["found"] is False and "已是" in result["message"]

        token, _ = stage("compliance_issue_update_status", manager, {"issue_id": issue.pk, "new_status": "处理中"})
        assert reject(manager, token).status_code == 200
        assert approve(manager, token).status_code == 409

    def test_invalid_status_is_rejected(self, manager, issue):
        result = dry_run("compliance_issue_update_status", manager, {"issue_id": issue.pk, "new_status": "已完成"})
        assert result["found"] is False and "已解决" in result["message"]
