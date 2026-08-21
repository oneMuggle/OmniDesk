"""用户菜单树缓存(R5-B1)。

键格式: user_menu_<user_pk>,值为 UserPermissionView 的响应数据(list[dict])。
失效兼容 LocMemCache 与 django_redis:按用户 pk 逐键删,不用 pattern 匹配。
"""

from django.core.cache import cache

MENU_CACHE_TIMEOUT = 300


def clear_user_menu_cache(user=None):
    """清除单个用户或全部用户的菜单缓存。"""
    if user is not None:
        cache.delete(f"user_menu_{user.pk}")
        return

    # 全量清除按全表 pk 删(菜单接口对任意已登录用户开放)
    from users.models import CustomUser

    pks = CustomUser.objects.values_list("pk", flat=True)
    cache.delete_many([f"user_menu_{pk}" for pk in pks])


def clear_menu_cache_for_group(group):
    """清除指定组下所有成员的菜单缓存。"""
    from users.models import CustomUser

    pks = CustomUser.objects.filter(groups=group).values_list("pk", flat=True)
    cache.delete_many([f"user_menu_{pk}" for pk in pks])
