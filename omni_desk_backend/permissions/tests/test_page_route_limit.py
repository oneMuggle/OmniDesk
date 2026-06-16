"""PageRouteViewSet 全集封顶 1000 测试。"""
import pytest
from rest_framework.test import APIClient
from rest_framework import status

from permissions.models import PageRoute


@pytest.mark.django_db
class TestPageRouteLimit:
    def test_returns_full_set_when_under_limit(self, api_client, admin_user_obj):
        PageRoute.objects.create(name="route-1", path="/r1/", component="Test", parent=None)
        PageRoute.objects.create(name="route-2", path="/r2/", component="Test", parent=None)
        api_client.force_authenticate(admin_user_obj)
        response = api_client.get("/api/permissions/pages/")
        assert response.status_code == status.HTTP_200_OK
        # pagination_class = None,响应始终为 list;无需 envelope 分支
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2  # 不触发封顶,完整返回

    def test_caps_at_1000_when_over_limit(self, api_client, admin_user_obj):
        """验证 PageRouteViewSet 列表在数据量 > 1000 时封顶到 1000。

        之前的测试只造 2 条数据后断言 `len(data) <= 1000`,无论实现是否封顶都通过。
        本测试用 bulk_create 高效造 1001 条 PageRoute,断言响应长度恰好等于 1000,
        实际触发并验证 list() 中的 queryset[:1000] 切片。
        """
        PageRoute.objects.bulk_create(
            [
                PageRoute(name=f"route-{i}", path=f"/r{i}/", component="TestComp", parent=None)
                for i in range(1001)
            ]
        )
        # 确认底层确实造了 1001 条,且全是 parent__isnull=True(viewset 的过滤条件)
        assert PageRoute.objects.filter(parent__isnull=True).count() == 1001

        api_client.force_authenticate(admin_user_obj)
        response = api_client.get("/api/permissions/pages/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # 关键断言:封顶到 1000,而非返回 1001 条
        assert len(data) == 1000
        # 次要断言:确实没有截到更低(确认是精确 1000 而非随意截断)
        assert len(data) < 1001
