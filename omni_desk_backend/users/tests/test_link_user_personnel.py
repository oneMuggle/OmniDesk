"""P1-4 link_user_personnel 管理命令 — TDD 测试(RED 阶段)

命令路径:omni_desk_backend/users/management/commands/link_user_personnel.py

支持:
- --strategy=username_to_name(默认):User.username == Personnel.name 匹配
- --dry-run: 预览不写库
- --unlink: 解绑(将 CustomUser.personnel 置 None)
- --batch=BATCH_ID: 指定批次号(默认自动生成)
- --rollback --batch=BATCH_ID: 按 batch_id 还原
"""
import datetime
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError

from personnel.models import Personnel
from users.models import AuditLogEntry

User = get_user_model()


@pytest.mark.django_db
class TestLinkByUsernameToName:
    """--strategy=username_to_name(默认):同名匹配"""

    def test_match_binds_user_to_personnel(self, regular_user_obj):
        """username == personnel.name 时应自动绑定。"""
        p = Personnel.objects.create(name=regular_user_obj.username)
        call_command("link_user_personnel", stdout=StringIO())
        regular_user_obj.refresh_from_db()
        assert regular_user_obj.personnel_id == p.id

    def test_no_match_skips_silently(self, regular_user_obj):
        """找不到匹配 personnel 时不应绑定。"""
        call_command("link_user_personnel", stdout=StringIO())
        regular_user_obj.refresh_from_db()
        assert regular_user_obj.personnel_id is None

    def test_already_linked_user_is_skipped(self, regular_user_obj):
        """用户已有关联 → 跳过(不应改变)。"""
        p_old = Personnel.objects.create(name=regular_user_obj.username)
        regular_user_obj.personnel = p_old
        regular_user_obj.save()
        p_new = Personnel.objects.create(name=regular_user_obj.username + "_other")
        call_command("link_user_personnel", stdout=StringIO())
        regular_user_obj.refresh_from_db()
        assert regular_user_obj.personnel_id == p_old.id  # 没被改


@pytest.mark.django_db
class TestLinkDryRun:
    """--dry-run 应只打印,不改库"""

    def test_dry_run_does_not_persist(self, regular_user_obj):
        Personnel.objects.create(name=regular_user_obj.username)
        out = StringIO()
        call_command("link_user_personnel", "--dry-run", stdout=out)
        regular_user_obj.refresh_from_db()
        assert regular_user_obj.personnel_id is None
        # 不写 audit log
        assert AuditLogEntry.objects.count() == 0

    def test_dry_run_output_contains_marker(self, regular_user_obj):
        Personnel.objects.create(name=regular_user_obj.username)
        out = StringIO()
        call_command("link_user_personnel", "--dry-run", stdout=out)
        text = out.getvalue()
        assert "Dry" in text or "预览" in text


@pytest.mark.django_db
class TestLinkAuditLog:
    """每次实际绑定都应写 audit log"""

    def test_link_writes_audit_log(self, regular_user_obj):
        p = Personnel.objects.create(name=regular_user_obj.username)
        out = StringIO()
        call_command("link_user_personnel", "--batch=B-TEST-1", stdout=out)
        entry = AuditLogEntry.objects.get(target_user=regular_user_obj)
        assert entry.action == AuditLogEntry.ACTION_LINK
        assert entry.batch_id == "B-TEST-1"
        assert entry.old_personnel_id is None
        assert entry.new_personnel_id == p.id

    def test_no_match_writes_link_skipped_log(self, regular_user_obj):
        out = StringIO()
        call_command("link_user_personnel", "--batch=B-SKIP", stdout=out)
        entry = AuditLogEntry.objects.get(target_user=regular_user_obj)
        assert entry.action == AuditLogEntry.ACTION_LINK_SKIPPED
        assert entry.batch_id == "B-SKIP"


@pytest.mark.django_db
class TestUnlink:
    """--unlink 应解绑"""

    def test_unlink_clears_personnel(self, regular_user_obj):
        p = Personnel.objects.create(name=regular_user_obj.username)
        regular_user_obj.personnel = p
        regular_user_obj.save()
        out = StringIO()
        call_command("link_user_personnel", "--unlink", "--batch=B-UN", stdout=out)
        regular_user_obj.refresh_from_db()
        assert regular_user_obj.personnel_id is None

    def test_unlink_dry_run_does_not_clear(self, regular_user_obj):
        p = Personnel.objects.create(name=regular_user_obj.username)
        regular_user_obj.personnel = p
        regular_user_obj.save()
        out = StringIO()
        call_command("link_user_personnel", "--unlink", "--dry-run", stdout=out)
        regular_user_obj.refresh_from_db()
        assert regular_user_obj.personnel_id == p.id

    def test_unlink_no_personnel_writes_skipped_log(self, regular_user_obj):
        out = StringIO()
        call_command("link_user_personnel", "--unlink", "--batch=B-UN-SKIP", stdout=out)
        entry = AuditLogEntry.objects.get(target_user=regular_user_obj)
        assert entry.action == AuditLogEntry.ACTION_UNLINK_SKIPPED


@pytest.mark.django_db
class TestRollback:
    """--rollback --batch=BATCH_ID 应还原"""

    def test_rollback_link_restores_user_state(self, regular_user_obj):
        """link 后回滚:user.personnel 应回到 link 之前(None)。"""
        p = Personnel.objects.create(name=regular_user_obj.username)
        out = StringIO()
        call_command("link_user_personnel", "--batch=B-RB-1", stdout=out)
        regular_user_obj.refresh_from_db()
        assert regular_user_obj.personnel_id == p.id

        call_command("link_user_personnel", "--rollback", "--batch=B-RB-1", stdout=StringIO())
        regular_user_obj.refresh_from_db()
        assert regular_user_obj.personnel_id is None

    def test_rollback_unknown_batch_raises(self):
        with pytest.raises(CommandError):
            call_command(
                "link_user_personnel", "--rollback", "--batch=B-NOT-EXIST", stdout=StringIO()
            )


@pytest.mark.django_db
class TestNotificationOnLink:
    """绑定成功应给用户发 ACCOUNT_LINKED 通知"""

    def test_link_creates_account_linked_notification(self, regular_user_obj):
        from notifications.models import Notification

        Personnel.objects.create(name=regular_user_obj.username)
        out = StringIO()
        call_command("link_user_personnel", stdout=out)
        notif = Notification.objects.filter(
            user=regular_user_obj, type="account_linked"
        ).first()
        assert notif is not None
        assert regular_user_obj.username in notif.content or "已关联" in notif.content
