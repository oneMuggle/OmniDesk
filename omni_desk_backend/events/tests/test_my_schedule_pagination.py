"""MyScheduleView 分页行为测试。

对应 PR-1 任务:验证移除 pagination_class = None 后,API 返回标准分页响应。
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from events.models import Schedule
from personnel.models import Personnel


@pytest.fixture
def regular_user(regular_user_obj):
    """Local alias to match plan signature; reuses global regular_user_obj."""
    return regular_user_obj


@pytest.fixture
def linked_personnel(regular_user):
    """为 regular_user 创建一个 Personnel 并关联 user.personnel。"""
    personnel = Personnel.objects.create(name=regular_user.username)
    regular_user.personnel = personnel
    regular_user.save()
    return personnel


@pytest.mark.django_db
class TestMySchedulePagination:
    """验证 MyScheduleView 已启用分页(移除 pagination_class = None)。"""

    def test_returns_paginated_envelope(self, api_client, regular_user, linked_personnel):
        """列表端点应返回 count/next/previous/results 字段(不是裸 list)。"""
        today = timezone.now().date()
        Schedule.objects.create(duty_date=today + timedelta(days=1), duty_person=linked_personnel)
        Schedule.objects.create(duty_date=today + timedelta(days=2), duty_person=linked_personnel)
        api_client.force_authenticate(regular_user)
        response = api_client.get("/api/events/me/schedule/")
        assert response.status_code == 200
        data = response.json()
        # 分页 envelope 必有字段
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert "results" in data
        assert data["count"] == 2
        assert len(data["results"]) == 2

    def test_no_personnel_returns_empty_envelope(self, api_client, regular_user):
        """user 无 personnel 关联时,应返回空分页 envelope(而非裸 [])。"""
        api_client.force_authenticate(regular_user)
        response = api_client.get("/api/events/me/schedule/")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []
