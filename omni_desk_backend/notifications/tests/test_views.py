import pytest
from django.urls import reverse
from rest_framework import status

from notifications.models import Notification
from users.models import CustomUser


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


@pytest.mark.django_db
class TestNotificationViewSet:
    def test_list_user_notifications(self, regular_client, regular_user_obj):
        Notification.objects.create(
            user=regular_user_obj, type='system', title='My notification', content='Content'
        )
        other_user = CustomUser.objects.create_user(username='other_user', password='pass123')
        Notification.objects.create(
            user=other_user, type='system', title='Other', content='Content'
        )

        response = regular_client.get(reverse('notification-list'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['title'] == 'My notification'

    def test_list_unauthenticated(self, api_client):
        response = api_client.get(reverse('notification-list'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_mark_as_read(self, regular_client, regular_user_obj):
        notification = Notification.objects.create(
            user=regular_user_obj, type='system', title='Test', content='Content', is_read=False
        )
        response = regular_client.patch(
            reverse('notification-mark-read', kwargs={'pk': notification.pk})
        )
        assert response.status_code == status.HTTP_200_OK
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_mark_all_as_read(self, regular_client, regular_user_obj):
        for i in range(3):
            Notification.objects.create(
                user=regular_user_obj, type='system', title=f'Notification {i}', content='Content', is_read=False
            )
        response = regular_client.post(reverse('notification-mark-all-read'))
        assert response.status_code == status.HTTP_200_OK
        assert Notification.objects.filter(user=regular_user_obj, is_read=False).count() == 0

    def test_unread_count(self, regular_client, regular_user_obj):
        for i in range(2):
            Notification.objects.create(
                user=regular_user_obj, type='system', title=f'Unread {i}', content='Content', is_read=False
            )
        Notification.objects.create(
            user=regular_user_obj, type='system', title='Read', content='Content', is_read=True
        )
        response = regular_client.get(reverse('notification-unread-count'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['unread_count'] == 2

    def test_cannot_access_other_user_notifications(self, regular_client, admin_user_obj):
        notification = Notification.objects.create(
            user=admin_user_obj, type='system', title='Admin notification', content='Content'
        )
        response = regular_client.get(reverse('notification-detail', kwargs={'pk': notification.pk}))
        assert response.status_code == status.HTTP_404_NOT_FOUND
