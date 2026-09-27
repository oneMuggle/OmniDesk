"""S3-2 两个写工具的完整流程测试：公告草稿、试验日程创建。

覆盖：批准、拒绝、重复提交、取消后再确认、撤销、撤销冲突、越权、参数错误，
以及试验时段冲突"提示但不阻止"。流程走真实接口：dry_run → approve / reject → revert。
"""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from events.models import Announcement, Equipment, TimeSlot, Trial
from notifications.models import Notification
from personnel.models import Personnel
from smart_assistant.models import AgentWriteLog

from .test_s3_write_tools import approve, dry_run, local_str, make_user, reject, revert, stage


@pytest.fixture(autouse=True)
def _run_tools_inline(settings):
    settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = False


def in_group(user, name):
    user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


@pytest.fixture
def admin(db):
    return in_group(make_user("s32-admin"), "Admin")


@pytest.fixture
def hr(db):
    return in_group(make_user("s32-hr"), "Manager")


@pytest.fixture
def staff(db):
    return make_user("s32-staff")


# ---------------------------------------------------------------------------
# 公告草稿
# ---------------------------------------------------------------------------

ANN = {"title": "国庆放假安排", "content": "10 月 1 日至 7 日放假，8 日正常上班。"}


@pytest.mark.django_db
class TestAnnouncementDraft:
    def test_preview_says_draft_and_permission_source(self, admin, hr):
        _, draft = stage("announcement_draft_create", admin, ANN)
        preview = draft["preview"]
        assert preview["action"] == "起草公告"
        assert preview["permission_source"] == "管理员"
        assert any("不会通知任何人" in w for w in preview["warnings"])
        assert "用户原话" not in str(preview)
        _, draft = stage("announcement_draft_create", hr, ANN)
        assert draft["preview"]["permission_source"] == "HR（经理组）"

    def test_approve_creates_draft_without_notifications_and_revert_deletes(self, admin, staff):
        token, _ = stage("announcement_draft_create", admin, ANN)
        response = approve(admin, token)
        assert response.status_code == 200, response.data
        announcement = Announcement.objects.get()
        assert announcement.status == Announcement.STATUS_DRAFT
        assert announcement.author == admin and announcement.published_at is None
        assert not Notification.objects.filter(type="announcement").exists()
        assert response.data["reversible"] is True

        assert revert(admin, response.data["write_log_id"]).status_code == 200
        assert not Announcement.objects.exists()
        assert AgentWriteLog.objects.get(pk=response.data["write_log_id"]).reverted_at is not None

    def test_staff_cannot_draft(self, staff):
        result = dry_run("announcement_draft_create", staff, ANN)
        assert result["found"] is False and "管理员或 HR" in result["message"]

    def test_permission_revoked_before_confirm(self, hr):
        token, _ = stage("announcement_draft_create", hr, ANN)
        hr.groups.clear()
        response = approve(hr, token)
        assert response.status_code == 400 and response.data["code"] == "permission_denied"
        assert not Announcement.objects.exists()

    def test_reject_duplicate_and_reject_then_confirm(self, admin):
        token, _ = stage("announcement_draft_create", admin, ANN)
        assert approve(admin, token).status_code == 200
        assert approve(admin, token).status_code == 409
        token2, _ = stage("announcement_draft_create", admin, ANN)
        assert reject(admin, token2).status_code == 200
        assert approve(admin, token2).status_code == 409
        assert Announcement.objects.count() == 1

    def test_revert_conflict_after_publish_or_edit(self, admin):
        token, _ = stage("announcement_draft_create", admin, ANN)
        log_id = approve(admin, token).data["write_log_id"]
        announcement = Announcement.objects.get()
        announcement.title = "改过的标题"
        announcement.save()
        response = revert(admin, log_id)
        assert response.status_code == 409 and "已被修改" in response.data["detail"]

        Announcement.objects.filter(pk=announcement.pk).update(status=Announcement.STATUS_PUBLISHED)
        response = revert(admin, log_id)
        assert response.status_code == 409 and "已发布" in response.data["detail"]
        assert Announcement.objects.exists()

    def test_other_admin_cannot_revert_my_log(self, admin):
        token, _ = stage("announcement_draft_create", admin, ANN)
        log_id = approve(admin, token).data["write_log_id"]
        other = in_group(make_user("s32-admin-2"), "Admin")
        assert revert(other, log_id).status_code == 404

    @pytest.mark.parametrize(
        "params, message",
        [
            ({"title": "", "content": "x"}, "标题"),
            ({"title": "t" * 201, "content": "x"}, "200"),
            ({"title": "t", "content": "  "}, "正文"),
        ],
    )
    def test_invalid_params(self, admin, params, message):
        result = dry_run("announcement_draft_create", admin, params)
        assert result["found"] is False and message in result["message"]


# ---------------------------------------------------------------------------
# 试验日程创建
# ---------------------------------------------------------------------------


def next_day(hour, days=2):
    base = timezone.localtime(timezone.now()).replace(hour=hour, minute=0, second=0, microsecond=0)
    return base + timedelta(days=days)


@pytest.fixture
def zhang(db):
    return Personnel.objects.create(name="张三", department="试验部")


@pytest.fixture
def shaker(db):
    return Equipment.objects.create(name="电动振动台 A", description="")


def trial_params(**overrides):
    params = {
        "title": "振动试验",
        "client": "某研究所",
        "description": "随机振动",
        "time_slots": [{"start_time": local_str(next_day(9)), "end_time": local_str(next_day(17))}],
        "responsible_persons": ["张三"],
        "equipments": ["电动振动台"],
    }
    params.update(overrides)
    return params


@pytest.mark.django_db
class TestTrialCreate:
    def test_preview_lists_slots_people_and_equipment(self, admin, zhang, shaker):
        _, draft = stage("trial_create", admin, trial_params())
        preview = draft["preview"]
        assert preview["target"]["label"] == "振动试验"
        changes = {c["field"]: c["after"] for c in preview["changes"]}
        assert changes["responsible_persons"] == "张三" and changes["equipments"] == "电动振动台 A"
        assert len(preview["items"]) == 1 and preview["warnings"] == []
        assert draft["fields"]["responsible_person_ids"] == [zhang.pk]
        assert draft["fields"]["equipment_ids"] == [shaker.pk]

    def test_approve_creates_trial_and_revert_deletes(self, hr, zhang, shaker):
        token, _ = stage("trial_create", hr, trial_params())
        response = approve(hr, token)
        assert response.status_code == 200, response.data
        trial = Trial.objects.get()
        assert trial.title == "振动试验" and trial.client == "某研究所"
        assert list(trial.responsible_persons.all()) == [zhang]
        assert list(trial.equipments.all()) == [shaker]
        assert trial.time_slots.count() == 1
        assert trial.start_date == next_day(9) and trial.end_date == next_day(17)

        assert revert(hr, response.data["write_log_id"]).status_code == 200
        assert not Trial.objects.exists() and not TimeSlot.objects.exists()

    def test_single_slot_flat_params_and_multiple_slots(self, admin, zhang):
        flat = trial_params(time_slots=None, start_time=local_str(next_day(9)), end_time=local_str(next_day(12)))
        _, draft = stage("trial_create", admin, {**flat, "equipments": []})
        assert len(draft["fields"]["time_slots"]) == 1

        slots = [
            {"start_time": local_str(next_day(14, 3)), "end_time": local_str(next_day(16, 3)), "description": "复测"},
            {"start_time": local_str(next_day(9)), "end_time": local_str(next_day(12))},
        ]
        token, draft = stage("trial_create", admin, trial_params(time_slots=slots, equipments=[]))
        assert draft["preview"]["items"][0].startswith(timezone.localtime(next_day(9)).strftime("%Y-%m-%d"))
        assert approve(admin, token).status_code == 200
        assert Trial.objects.get().time_slots.count() == 2

    def test_conflicts_are_warned_but_confirmable(self, admin, zhang, shaker):
        existing = Trial.objects.create(title="热真空试验", client="c", description="d")
        existing.equipments.add(shaker)
        TimeSlot.objects.create(trial=existing, start_time=next_day(13), end_time=next_day(20))
        cancelled = Trial.objects.create(title="已取消的试验", client="c", description="d", status="cancelled")
        cancelled.responsible_persons.add(zhang)
        TimeSlot.objects.create(trial=cancelled, start_time=next_day(10), end_time=next_day(11))

        token, draft = stage("trial_create", admin, trial_params())
        warnings = draft["preview"]["warnings"]
        assert len(warnings) == 1
        assert "热真空试验" in warnings[0] and "电动振动台 A" in warnings[0]
        response = approve(admin, token)
        assert response.status_code == 200
        assert "1 个试验存在时段冲突" in response.data["answer"]
        assert Trial.objects.count() == 3

    def test_staff_cannot_create(self, staff, zhang, shaker):
        result = dry_run("trial_create", staff, trial_params())
        assert result["found"] is False and "管理员或 HR" in result["message"]

    @pytest.mark.parametrize(
        "overrides, message",
        [
            ({"title": ""}, "试验名称"),
            ({"time_slots": []}, "试验时间"),
            ({"time_slots": [{"start_time": "明天", "end_time": "后天"}]}, "格式不正确"),
            ({"time_slots": [{"start_time": "2026-10-08T17:00", "end_time": "2026-10-08T09:00"}]}, "晚于开始"),
            (
                {
                    "time_slots": [
                        {"start_time": "2026-10-08T09:00", "end_time": "2026-10-08T12:00"},
                        {"start_time": "2026-10-08T11:00", "end_time": "2026-10-08T13:00"},
                    ]
                },
                "重叠",
            ),
            ({"responsible_persons": ["李四"]}, "没有找到名为「李四」的人员"),
            ({"equipments": ["不存在的设备"]}, "没有找到名为「不存在的设备」的设备"),
        ],
    )
    def test_invalid_params(self, admin, zhang, shaker, overrides, message):
        result = dry_run("trial_create", admin, trial_params(**overrides))
        assert result["found"] is False and message in result["message"], result

    def test_duplicate_names_are_listed(self, admin, zhang, shaker):
        Personnel.objects.create(name="张三", department="质量部")
        result = dry_run("trial_create", admin, trial_params())
        assert result["found"] is False and "多名叫「张三」" in result["message"]
        assert "试验部" in result["message"] and "质量部" in result["message"]

    def test_ambiguous_equipment(self, admin, zhang, shaker):
        Equipment.objects.create(name="电动振动台 B", description="")
        result = dry_run("trial_create", admin, trial_params())
        assert result["found"] is False and "匹配到多台设备" in result["message"]

    def test_deleted_person_before_confirm_is_409(self, admin, zhang, shaker):
        token, _ = stage("trial_create", admin, trial_params())
        zhang.delete()
        response = approve(admin, token)
        assert response.status_code == 409 and response.data["code"] == "stale_confirmation"
        assert not Trial.objects.exists()

    def test_duplicate_reject_and_revoked_permission(self, admin, zhang, shaker):
        token, _ = stage("trial_create", admin, trial_params())
        assert approve(admin, token).status_code == 200
        assert approve(admin, token).status_code == 409
        token2, _ = stage("trial_create", admin, trial_params())
        assert reject(admin, token2).status_code == 200
        assert approve(admin, token2).status_code == 409
        token3, _ = stage("trial_create", admin, trial_params())
        admin.groups.clear()
        assert approve(admin, token3).status_code == 400
        assert Trial.objects.count() == 1

    def test_revert_conflict_when_trial_edited(self, admin, zhang, shaker):
        token, _ = stage("trial_create", admin, trial_params())
        log_id = approve(admin, token).data["write_log_id"]
        trial = Trial.objects.get()
        Trial.objects.filter(pk=trial.pk).update(version=1, title="改过的名称")
        response = revert(admin, log_id)
        assert response.status_code == 409 and "已被修改" in response.data["detail"]
        assert Trial.objects.exists()

    def test_revert_conflict_when_slot_added(self, admin, zhang, shaker):
        token, _ = stage("trial_create", admin, trial_params())
        log_id = approve(admin, token).data["write_log_id"]
        TimeSlot.objects.create(trial=Trial.objects.get(), start_time=next_day(9, 5), end_time=next_day(10, 5))
        assert revert(admin, log_id).status_code == 409

    def test_revert_requires_permission(self, admin, zhang, shaker):
        token, _ = stage("trial_create", admin, trial_params())
        log_id = approve(admin, token).data["write_log_id"]
        admin.groups.clear()
        response = revert(admin, log_id)
        assert response.status_code == 409 and "权限" in response.data["detail"]
