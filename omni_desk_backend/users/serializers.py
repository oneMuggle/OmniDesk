"""用户模块序列化器入口。

权限逻辑在此文件中维护，具体序列化器定义在：
- user_serializers.py：用户详情、列表、管理
- auth_serializers.py：注册、登录、JWT、Guest
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from rest_framework import serializers

from permissions.models import GroupPagePermission
from personnel.models import Position

# Re-export all serializers for backward compatibility
from .user_serializers import (
    PhoneNumberSerializer,
    UserDetailSerializer,
    UserSerializer,
    UserAdminSerializer,
    UserPersonnelSerializer,
)
from .auth_serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
    GuestLoginSerializer,
    ensure_guest_group,
)

CustomUser = get_user_model()

_PERMISSION_CACHE_TIMEOUT = 3600  # 1 hour


def get_user_permissions(user):
    """
    获取用户的所有权限，包括标准的Django权限和自定义页面权限。
    使用 Redis 缓存（多 worker 共享），替代 lru_cache。
    """
    cache_key = f'user_permissions_{user.pk}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    permissions = set(user.get_all_permissions())
    if user.is_staff or user.is_superuser:
        permissions.add('admin')

    user_groups = user.groups.all()
    group_names = set(user_groups.values_list('name', flat=True))
    group_ids = list(user_groups.values_list('id', flat=True))

    if group_ids:
        for gid in group_ids:
            permissions.update(_get_group_page_permissions(gid))

    if 'Admin' in group_names:
        permissions.add('events.manage_schedule')
        permissions.add('documents.view_book')

    if 'Manager' in group_names:
        permissions.add('manager')
        permissions.add('events.manage_personnel')

    result = list(permissions)
    cache.set(cache_key, result, _PERMISSION_CACHE_TIMEOUT)
    return result


def clear_user_permissions_cache(user=None):
    """清除权限缓存，在修改用户权限后调用"""
    if user:
        cache.delete(f'user_permissions_{user.pk}')
    else:
        # 清除所有用户权限缓存（使用 pattern matching）
        cache.delete_many([key for key in cache.iter_keys('user_permissions_*')])


def _get_group_page_permissions(group_id):
    """获取单个组的页面权限，使用缓存"""
    cache_key = f'group_permissions_{group_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    perms = set(
        GroupPagePermission.objects.filter(group_id=group_id).values_list('page__path', flat=True)
    )
    cache.set(cache_key, perms, _PERMISSION_CACHE_TIMEOUT)
    return perms


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = '__all__'
