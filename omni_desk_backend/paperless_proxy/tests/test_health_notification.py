"""P0-H paperless 健康检查管理面通知测试

- 连续失败越过阈值 → 全体 admin 收到 paperless_down 紧急通知
- 阈值前不告警;恢复后收到 paperless_recovered
- 普通用户不收管理面告警
"""
from unittest.mock import patch

import pytest
from django.conf import settings

from notifications.models import Notification
from paperless_proxy.tasks import check_paperless_health
from users.models import CustomUser


@pytest.fixture
def plain_user(db):
    return CustomUser.objects.create_user(username="plain_user_ppl", password="pass12345")


@pytest.mark.django_db
class TestHealthNotification:
    def test_admins_notified_when_paperless_goes_down(self, admin_user_obj, plain_user):
        threshold = settings.PAPERLESS_HEALTH_FAILURE_THRESHOLD
        with patch("paperless_proxy.services.client.PaperlessClient.health_check", return_value=False):
            for _ in range(threshold):
                check_paperless_health()

        downs = Notification.objects.filter(type="paperless_down")
        assert downs.exists()
        note = downs.first()
        assert note.user_id == admin_user_obj.id
        assert note.priority == Notification.PRIORITY_URGENT
        assert note.dedupe_key.startswith("paperless_down:")
        # 普通用户不收管理面告警
        assert not Notification.objects.filter(type="paperless_down", user=plain_user).exists()

    def test_no_notification_before_threshold(self, admin_user_obj):
        threshold = settings.PAPERLESS_HEALTH_FAILURE_THRESHOLD
        with patch("paperless_proxy.services.client.PaperlessClient.health_check", return_value=False):
            for _ in range(threshold - 1):
                check_paperless_health()

        assert not Notification.objects.filter(type="paperless_down").exists()

    def test_admins_notified_on_recovery(self, admin_user_obj):
        threshold = settings.PAPERLESS_HEALTH_FAILURE_THRESHOLD
        with patch("paperless_proxy.services.client.PaperlessClient.health_check", return_value=False):
            for _ in range(threshold):
                check_paperless_health()

        with patch("paperless_proxy.services.client.PaperlessClient.health_check", return_value=True):
            check_paperless_health()

        recovered = Notification.objects.filter(type="paperless_recovered")
        assert recovered.exists()
        assert recovered.first().user_id == admin_user_obj.id

    def test_steady_healthy_does_not_notify(self, admin_user_obj):
        with patch("paperless_proxy.services.client.PaperlessClient.health_check", return_value=True):
            check_paperless_health()
            check_paperless_health()

        assert not Notification.objects.filter(type__in=["paperless_down", "paperless_recovered"]).exists()
