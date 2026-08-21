"""R5-B1: UserPermissionView 菜单树缓存测试。

验证:
1. 首次请求后写入 user_menu_<pk> 缓存
2. 第二次请求命中缓存(不再打 DB)
3. GroupPagePermission 变更后对应组用户的缓存被失效
4. PageRoute 变更后全部用户缓存被失效
5. 用户 groups m2m 变更后该用户缓存被失效
"""

import pytest
from django.contrib.auth.models import Group
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser

from ..models import GroupPagePermission, PageRoute

pytestmark = pytest.mark.django_db

MENU_CACHE_TIMEOUT = 300


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user_group(db):
    return Group.objects.create(name="MenuUserGroup")


@pytest.fixture
def member(db, user_group):
    user = CustomUser.objects.create_user(username="menu_member", password="pass123")
    user.groups.add(user_group)
    return user


@pytest.fixture
def member_client(api_client, member):
    api_client.force_authenticate(user=member)
    return api_client


@pytest.fixture
def page(db):
    return PageRoute.objects.create(name="菜单页", path="/menu-page", component="MenuPage")


class TestUserPermissionCache:
    def test_response_populates_cache(self, member_client, member, user_group, page):
        GroupPagePermission.objects.create(group=user_group, page=page)
        response = member_client.get("/api/permissions/users/me/permissions/")
        assert response.status_code == status.HTTP_200_OK
        assert cache.get(f"user_menu_{member.pk}") is not None

    def test_second_request_hits_cache(self, member_client, member, user_group, page):
        GroupPagePermission.objects.create(group=user_group, page=page)
        assert member_client.get("/api/permissions/users/me/permissions/").status_code == 200

        # 直接改写缓存内容为哨兵值:若第二次请求命中缓存,响应应等于哨兵而非真实数据
        sentinel = [
            {
                "id": -999,
                "name": "sentinel",
                "path": "/sentinel",
                "component": "S",
                "parent": None,
                "children": [],
            }
        ]
        cache.set(f"user_menu_{member.pk}", sentinel, MENU_CACHE_TIMEOUT)
        response = member_client.get("/api/permissions/users/me/permissions/")
        assert response.data == sentinel

    def test_superuser_response_populates_cache(self, api_client, db, page):
        admin = CustomUser.objects.create_user(username="menu_admin", password="pass123", is_superuser=True)
        api_client.force_authenticate(user=admin)
        assert api_client.get("/api/permissions/users/me/permissions/").status_code == 200
        assert cache.get(f"user_menu_{admin.pk}") is not None

    def test_group_page_permission_change_invalidates_member_cache(self, member_client, member, user_group, page):
        # 第一次请求建立缓存(此时无权限,菜单为空)
        assert member_client.get("/api/permissions/users/me/permissions/").status_code == 200
        assert cache.get(f"user_menu_{member.pk}") == []

        # 授权后缓存必须失效,再次请求应看到新页面
        GroupPagePermission.objects.create(group=user_group, page=page)
        assert cache.get(f"user_menu_{member.pk}") is None
        response = member_client.get("/api/permissions/users/me/permissions/")
        assert any(p["id"] == page.id for p in response.data)

    def test_page_route_change_invalidates_all_caches(self, api_client, member_client, member, page):
        assert member_client.get("/api/permissions/users/me/permissions/").status_code == 200
        other = CustomUser.objects.create_user(username="menu_other", password="pass123", is_superuser=True)
        api_client.force_authenticate(user=other)
        assert api_client.get("/api/permissions/users/me/permissions/").status_code == 200
        assert cache.get(f"user_menu_{member.pk}") is not None
        assert cache.get(f"user_menu_{other.pk}") is not None

        # 路由表变更 → 全员缓存失效
        page.name = "改名后的菜单页"
        page.save()
        assert cache.get(f"user_menu_{member.pk}") is None
        assert cache.get(f"user_menu_{other.pk}") is None

    def test_group_membership_change_invalidates_user_cache(self, member, user_group, page):
        GroupPagePermission.objects.create(group=user_group, page=page)
        client = APIClient()
        client.force_authenticate(member)
        assert client.get("/api/permissions/users/me/permissions/").status_code == 200
        assert cache.get(f"user_menu_{member.pk}") is not None

        # 移出组 → 该用户缓存失效
        member.groups.clear()
        assert cache.get(f"user_menu_{member.pk}") is None


class TestClearHelper:
    def test_clear_single_user(self, member):
        from ..cache import clear_user_menu_cache

        cache.set(f"user_menu_{member.pk}", [1], MENU_CACHE_TIMEOUT)
        cache.set("user_menu_999999", [1], MENU_CACHE_TIMEOUT)
        clear_user_menu_cache(member)
        assert cache.get(f"user_menu_{member.pk}") is None
        assert cache.get("user_menu_999999") == [1]

    def test_clear_all_users(self, api_client, member):
        from ..cache import clear_user_menu_cache

        other = CustomUser.objects.create_user(username="menu_all_other", password="pass123")
        cache.set(f"user_menu_{member.pk}", [1], MENU_CACHE_TIMEOUT)
        cache.set(f"user_menu_{other.pk}", [1], MENU_CACHE_TIMEOUT)
        clear_user_menu_cache()
        assert cache.get(f"user_menu_{member.pk}") is None
        assert cache.get(f"user_menu_{other.pk}") is None
