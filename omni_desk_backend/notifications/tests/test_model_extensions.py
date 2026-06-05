"""P1-1 扩展 Notification 模型 — TDD 测试(RED 阶段)

新字段:
- priority: 优先级(LOW=1 / NORMAL=2 / HIGH=3 / URGENT=4),默认 NORMAL
- dedupe_key: 去重键(字符串),空表示不去重
- read_at: 已读时间,可空

遵循 TDD 流程:先写测试,运行确认失败,再实现。
"""
import pytest
from django.db import models as django_models

from notifications.models import Notification


@pytest.mark.django_db
class TestNotificationPriorityField:
    """priority 字段应存在,默认为 NORMAL=2,枚举包含 LOW/NORMAL/HIGH/URGENT。"""

    def test_priority_field_exists(self):
        field = Notification._meta.get_field("priority")
        assert field is not None
        assert isinstance(field, django_models.PositiveSmallIntegerField)

    def test_priority_default_is_normal(self, regular_user_obj):
        notification = Notification.objects.create(
            user=regular_user_obj,
            type="system",
            title="t",
            content="c",
        )
        assert notification.priority == 2  # NORMAL

    def test_priority_choices_contain_expected_values(self):
        field = Notification._meta.get_field("priority")
        # PositiveSmallIntegerField 的 choices 元组首元素为 int 而非 str
        values = {choice[0] for choice in field.choices}
        assert values == {1, 2, 3, 4}

    def test_priority_can_be_set_explicitly(self, regular_user_obj):
        notification = Notification.objects.create(
            user=regular_user_obj,
            type="system",
            title="t",
            content="c",
            priority=4,  # URGENT
        )
        assert notification.priority == 4


@pytest.mark.django_db
class TestNotificationDedupeKeyField:
    """dedupe_key 字段应存在,默认空字符串,带 db_index。"""

    def test_dedupe_key_field_exists(self):
        field = Notification._meta.get_field("dedupe_key")
        assert field is not None
        assert isinstance(field, django_models.CharField)
        assert field.db_index is True
        assert field.blank is True

    def test_dedupe_key_default_is_empty_string(self, regular_user_obj):
        notification = Notification.objects.create(
            user=regular_user_obj,
            type="system",
            title="t",
            content="c",
        )
        assert notification.dedupe_key == ""

    def test_dedupe_key_can_be_set(self, regular_user_obj):
        notification = Notification.objects.create(
            user=regular_user_obj,
            type="schedule_change",
            title="t",
            content="c",
            dedupe_key="duty:123:created",
        )
        assert notification.dedupe_key == "duty:123:created"


@pytest.mark.django_db
class TestNotificationReadAtField:
    """read_at 字段应存在,可空。"""

    def test_read_at_field_exists(self):
        field = Notification._meta.get_field("read_at")
        assert field is not None
        assert isinstance(field, django_models.DateTimeField)
        assert field.null is True
        assert field.blank is True

    def test_read_at_defaults_to_null(self, regular_user_obj):
        notification = Notification.objects.create(
            user=regular_user_obj,
            type="system",
            title="t",
            content="c",
        )
        assert notification.read_at is None
