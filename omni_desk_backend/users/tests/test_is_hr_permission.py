"""P2-2 IsHR 权限类 — TDD 测试(RED 阶段)

IsHR 等价于"Manager 组 + change_personnel 权限"。
但项目默认 Manager 组无显式权限(permissions 体系稍后展开),
所以 IsHR 第一版实现:Manager 组 OR superuser。
"""
import pytest
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from users.permissions import IsHR


def _make_request(user):
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = user
    return request


@pytest.mark.django_db
class TestIsHRPermission:
    def test_manager_user_passes(self, manager_user_obj):
        request = _make_request(manager_user_obj)
        view = APIView()
        assert IsHR().has_permission(request, view) is True

    def test_admin_user_passes(self, admin_user_obj):
        """Admin 也是 HR(因业务上 Admin 包含 HR 能力)。"""
        request = _make_request(admin_user_obj)
        view = APIView()
        assert IsHR().has_permission(request, view) is True

    def test_regular_user_fails(self, regular_user_obj):
        request = _make_request(regular_user_obj)
        view = APIView()
        assert IsHR().has_permission(request, view) is False

    def test_anonymous_user_fails(self):
        from django.contrib.auth.models import AnonymousUser
        request = _make_request(AnonymousUser())
        view = APIView()
        assert IsHR().has_permission(request, view) is False
