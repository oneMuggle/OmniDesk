import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
class TestDashboardStats:
    def test_dashboard_stats_returns_data(self, regular_client, regular_user_obj):
        response = regular_client.get(reverse('dashboard-stats'))
        assert response.status_code == status.HTTP_200_OK
        assert 'today_schedule' in response.data
        assert 'recent_announcements' in response.data
        assert 'memos_due' in response.data
        assert 'projects' in response.data
        assert 'unread_notifications' in response.data

    def test_dashboard_stats_unauthenticated(self, api_client):
        response = api_client.get(reverse('dashboard-stats'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
