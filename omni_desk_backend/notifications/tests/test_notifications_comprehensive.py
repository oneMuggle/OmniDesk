"""notifications 模块补充测试。"""

import pytest

from notifications.models import Notification
from users.models import CustomUser


@pytest.mark.django_db
class TestNotificationViewSet:
    def test_notification_list(self, admin_client, admin_user_obj):
        """通知列表"""
        Notification.objects.create(
            user=admin_user_obj,
            type='system',
            title='测试通知',
            content='这是一条测试通知',
        )
        resp = admin_client.get('/api/notifications/')
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1

    def test_mark_as_read(self, admin_client, admin_user_obj):
        """标记已读"""
        notif = Notification.objects.create(
            user=admin_user_obj,
            type='system',
            title='未读通知',
            content='内容',
            is_read=False,
        )
        resp = admin_client.patch(f'/api/notifications/{notif.id}/', {
            'is_read': True,
        }, format='json')
        assert resp.status_code in [200, 204]

    def test_unread_count(self, admin_client, admin_user_obj):
        """未读计数"""
        Notification.objects.create(user=admin_user_obj, type='system', title='未读1', content='内容1', is_read=False)
        Notification.objects.create(user=admin_user_obj, type='system', title='未读2', content='内容2', is_read=False)
        resp = admin_client.get('/api/notifications/unread_count/')
        assert resp.status_code == 200
