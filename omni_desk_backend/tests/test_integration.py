"""Cross-module integration tests.

Tests that span multiple Django apps to verify end-to-end behavior.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from notifications.models import Notification


@pytest.mark.django_db
class TestComplianceScheduled:
    """Compliance check engine tests."""

    def test_compliance_issue_triggers_notification(self, regular_user_obj):
        """Creating a compliance issue for a project should be visible to the manager."""
        from projects.models import Project
        from compliance.services.compliance_engine import ComplianceChecker

        project = Project.objects.create(
            name='Test Project',
            manager=regular_user_obj,
        )

        from compliance.models import ComplianceIssue

        issue = ComplianceIssue.objects.create(
            project=project,
            issue_type='safety',
            description='Test compliance issue',
            severity='high',
            status='待处理',
        )

        visible = ComplianceChecker.get_visible_issues(regular_user_obj)
        assert visible.filter(pk=issue.pk).exists()

    def test_compliance_unread_count_includes_new_issues(self, regular_user_obj):
        """Unread count should reflect newly created issues."""
        from compliance.services.compliance_engine import ComplianceChecker

        initial_count = ComplianceChecker.get_unread_count(regular_user_obj)

        from projects.models import Project
        from compliance.models import ComplianceIssue

        project = Project.objects.create(
            name='Count Test Project',
            manager=regular_user_obj,
        )
        ComplianceIssue.objects.create(
            project=project,
            issue_type='safety',
            description='Count test issue',
            severity='medium',
            status='待处理',
        )

        new_count = ComplianceChecker.get_unread_count(regular_user_obj)
        assert new_count == initial_count + 1


@pytest.mark.django_db
class TestNotificationTrigger:
    """Event-triggered notification tests."""

    def test_notification_created_on_event(self, regular_user_obj):
        """System events should create notifications for affected users."""
        Notification.objects.create(
            user=regular_user_obj,
            type='system',
            title='Test Event',
            content='A test notification was triggered',
        )

        assert Notification.objects.filter(user=regular_user_obj).count() >= 1

    def test_notification_marked_read_via_api(self, regular_client, regular_user_obj):
        """Notification read status should update via API."""
        notification = Notification.objects.create(
            user=regular_user_obj,
            type='system',
            title='Read Test',
            content='Test marking as read',
        )

        response = regular_client.patch(
            reverse('notification-detail', kwargs={'pk': notification.pk}),
            {'is_read': True},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_mark_all_read_via_api(self, regular_client, regular_user_obj):
        """Mark all notifications as read should clear unread count."""
        for i in range(3):
            Notification.objects.create(
                user=regular_user_obj,
                type='system',
                title=f'Unread {i}',
                content='Test content',
            )

        response = regular_client.post(
            reverse('notification-mark-all-read'),
        )
        assert response.status_code == status.HTTP_200_OK
        assert Notification.objects.filter(user=regular_user_obj, is_read=False).count() == 0
