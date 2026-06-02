"""permissions 模块补充测试。"""

import pytest

from permissions.models import PageRoute, GroupPagePermission
from django.contrib.auth.models import Group


@pytest.mark.django_db
class TestPageRouteViewSet:
    def test_page_route_list(self, admin_client):
        """页面路由列表（只读）"""
        PageRoute.objects.create(name='测试页面', path='/test-page', component='TestPage')
        resp = admin_client.get('/api/permissions/pages/')
        assert resp.status_code == 200
        results = resp.data if isinstance(resp.data, list) else resp.data.get('results', [])
        assert len(results) >= 1

    def test_page_route_detail(self, admin_client):
        """页面路由详情"""
        page = PageRoute.objects.create(name='详情页面', path='/detail-page', component='DetailPage')
        resp = admin_client.get(f'/api/permissions/pages/{page.id}/')
        assert resp.status_code == 200
        assert resp.data['name'] == '详情页面'


@pytest.mark.django_db
class TestGroupViewSet:
    def test_group_crud(self, admin_client):
        """用户组 CRUD"""
        resp = admin_client.post('/api/permissions/groups/', {'name': '测试组'}, format='json')
        assert resp.status_code == 201, resp.data
        group_id = resp.data['id']

        resp = admin_client.delete(f'/api/permissions/groups/{group_id}/')
        assert resp.status_code == 204
