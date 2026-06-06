"""P1-5 AuditLogEntry 模型 — TDD 测试(RED 阶段)

AuditLogEntry 放在 users/models.py(与 link_user_personnel 命令同模块)。

字段:
- batch_id: 字符串(用于按批次回滚),db_index
- actor: 字符串(操作者标识,如 'cli:admin01' 或 'admin:user_id:12')
- action: 字符串(link / unlink / link_skipped / unlink_skipped)
- target_user: FK → CustomUser
- old_personnel_id / new_personnel_id: 整型可空(关联前/后状态)
- metadata: JSONField(扩展信息,如匹配策略、csv 路径等)
- created_at: DateTimeField(auto_now_add)
"""
import pytest
from django.db import models as django_models
from django.contrib.auth import get_user_model

from users.models import AuditLogEntry

User = get_user_model()


@pytest.mark.django_db
class TestAuditLogEntryModel:
    def test_field_types(self):
        """字段类型应符合设计。"""
        batch_id = AuditLogEntry._meta.get_field("batch_id")
        assert isinstance(batch_id, django_models.CharField)
        assert batch_id.db_index is True
        assert batch_id.max_length == 64

        actor = AuditLogEntry._meta.get_field("actor")
        assert isinstance(actor, django_models.CharField)
        assert actor.max_length == 100
        assert actor.blank is True

        action = AuditLogEntry._meta.get_field("action")
        assert isinstance(action, django_models.CharField)
        assert action.max_length == 32

        target_user = AuditLogEntry._meta.get_field("target_user")
        assert isinstance(target_user, django_models.ForeignKey)
        assert target_user.related_model is User
        assert target_user.remote_field.on_delete.__name__ == "CASCADE"

        old_pid = AuditLogEntry._meta.get_field("old_personnel_id")
        assert isinstance(old_pid, django_models.IntegerField)
        assert old_pid.null is True

        new_pid = AuditLogEntry._meta.get_field("new_personnel_id")
        assert isinstance(new_pid, django_models.IntegerField)
        assert new_pid.null is True

        meta = AuditLogEntry._meta.get_field("metadata")
        assert isinstance(meta, django_models.JSONField)
        assert meta.default == dict

        created_at = AuditLogEntry._meta.get_field("created_at")
        assert isinstance(created_at, django_models.DateTimeField)
        assert created_at.auto_now_add is True

    def test_create_entry(self, regular_user_obj):
        """应能创建一条审计日志。"""
        entry = AuditLogEntry.objects.create(
            batch_id="2026-06-05-001",
            actor="cli:admin01",
            action="link",
            target_user=regular_user_obj,
            old_personnel_id=None,
            new_personnel_id=345,
            metadata={"strategy": "manual", "csv": "/tmp/m.csv"},  # nosec B108 - 测试占位路径,非真实文件
        )
        assert entry.pk is not None
        assert entry.batch_id == "2026-06-05-001"
        assert entry.action == "link"
        assert entry.metadata == {"strategy": "manual", "csv": "/tmp/m.csv"}  # nosec B108 - 测试占位路径

    def test_query_by_batch_id(self, regular_user_obj):
        """应能按 batch_id 查询所有相关日志。"""
        AuditLogEntry.objects.create(
            batch_id="B-1", actor="cli:a", action="link", target_user=regular_user_obj, new_personnel_id=1
        )
        AuditLogEntry.objects.create(
            batch_id="B-1", actor="cli:a", action="link", target_user=regular_user_obj, new_personnel_id=2
        )
        AuditLogEntry.objects.create(
            batch_id="B-2", actor="cli:b", action="unlink", target_user=regular_user_obj, old_personnel_id=3
        )
        assert AuditLogEntry.objects.filter(batch_id="B-1").count() == 2
        assert AuditLogEntry.objects.filter(batch_id="B-2").count() == 1

    def test_cascade_delete_with_user(self, regular_user_obj):
        """target_user 删除时,审计日志应级联删除。"""
        AuditLogEntry.objects.create(
            batch_id="B-1", actor="cli:a", action="link", target_user=regular_user_obj
        )
        user_id = regular_user_obj.pk
        assert AuditLogEntry.objects.filter(target_user_id=user_id).count() == 1
        regular_user_obj.delete()
        assert AuditLogEntry.objects.filter(target_user_id=user_id).count() == 0
