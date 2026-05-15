import pytest

from notifications.models import Notification


@pytest.mark.django_db
class TestNotificationModel:
    def test_notification_creation(self, regular_user_obj):
        notification = Notification.objects.create(
            user=regular_user_obj,
            type='system',
            title='Test notification',
            content='Test content',
        )
        assert notification.pk is not None
        assert notification.is_read is False
        assert notification.is_system is False

    def test_notification_str(self, regular_user_obj):
        notification = Notification.objects.create(
            user=regular_user_obj,
            type='schedule_change',
            title='Shift changed',
            content='Your shift has been changed',
        )
        assert str(notification) == '[排班变更] Shift changed'

    def test_default_values(self, regular_user_obj):
        notification = Notification.objects.create(
            user=regular_user_obj,
            type='system',
            title='Title',
            content='Content',
        )
        assert notification.is_read is False
        assert notification.is_system is False
        assert notification.link == ''
