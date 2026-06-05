"""P1-2 NotificationPreference 模型 — TDD 测试(先写测试,后实现已落地)

NotificationPreference 是 OneToOneField → CustomUser,字段:
- quiet_hours_start / quiet_hours_end: TimeField(可空)
- channel_settings: JSONField(默认空 dict)
- created_at / updated_at: 自动维护
"""
import pytest
from django.db import models as django_models

from notifications.models import NotificationPreference


@pytest.mark.django_db
class TestNotificationPreferenceModel:
    def test_field_types(self):
        """所有字段类型应符合设计。"""
        user_field = NotificationPreference._meta.get_field("user")
        assert isinstance(user_field, django_models.OneToOneField)
        assert user_field.remote_field.model.__name__ == "CustomUser"

        quiet_start = NotificationPreference._meta.get_field("quiet_hours_start")
        assert isinstance(quiet_start, django_models.TimeField)
        assert quiet_start.null is True
        assert quiet_start.blank is True

        quiet_end = NotificationPreference._meta.get_field("quiet_hours_end")
        assert isinstance(quiet_end, django_models.TimeField)
        assert quiet_end.null is True
        assert quiet_end.blank is True

        channel = NotificationPreference._meta.get_field("channel_settings")
        assert isinstance(channel, django_models.JSONField)
        assert channel.default == dict
        assert channel.blank is True

    def test_create_with_defaults(self, regular_user_obj):
        """channel_settings 默认值应为 {}。"""
        pref = NotificationPreference.objects.create(user=regular_user_obj)
        assert pref.channel_settings == {}
        assert pref.quiet_hours_start is None
        assert pref.quiet_hours_end is None

    def test_one_to_one_constraint(self, regular_user_obj):
        """同一用户只能创建一个 NotificationPreference。"""
        NotificationPreference.objects.create(user=regular_user_obj)
        with pytest.raises(Exception):  # IntegrityError
            NotificationPreference.objects.create(user=regular_user_obj)

    def test_reverse_access_from_user(self, regular_user_obj):
        """应能通过 user.notification_pref 反向访问。"""
        pref = NotificationPreference.objects.create(
            user=regular_user_obj,
            channel_settings={"email": {"schedule_change": True}},
        )
        assert regular_user_obj.notification_pref == pref
        assert regular_user_obj.notification_pref.channel_settings == {
            "email": {"schedule_change": True}
        }

    def test_str_representation(self, regular_user_obj):
        """__str__ 应返回'通知偏好:用户名'。"""
        pref = NotificationPreference.objects.create(user=regular_user_obj)
        assert str(pref) == f"通知偏好:{regular_user_obj.username}"
