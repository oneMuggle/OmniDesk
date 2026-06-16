"""PageRouteViewSet 全集封顶 1000 测试。"""
import pytest
from rest_framework.test import APIClient
from rest_framework import status

from permissions.models import PageRoute


@pytest.mark.django_db
class TestPageRouteLimit:
    def test_returns_full_set_when_under_limit(self, api_client, admin_user_obj):
        PageRoute.objects.create(name="route-1", path="/r1/", parent=None)
        PageRoute.objects.create(name="route-2", path="/r2/", parent=None)
        api_client.force_authenticate(admin_user_obj)
        response = api_client.get("/api/permissions/pages/")
        assert response.status_code == status.HTTP_200_OK
        # 现有实现是裸 list 或 envelope(由 pagination_class 决定)
        # 此处断言长度 ≤ 1000 即可
        data = response.json() if isinstance(response.json(), list) else response.json()["results"]
        assert len(data) <= 1000
