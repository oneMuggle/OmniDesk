"""菜单缓存失效信号(R5-B1)。

三个失效触发点:
1. GroupPagePermission 变更 → 清该组所有成员的缓存
2. PageRoute 变更(路由树变了) → 清全部用户缓存
3. User.groups m2m 变更 → 清该用户缓存
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .cache import clear_menu_cache_for_group, clear_user_menu_cache
from .models import GroupPagePermission, PageRoute

# CustomUser.groups 的 related_name 被覆盖为 custom_user_groups(修复反向访问器冲突),
# m2m through 表须从模型字段动态取,不能用 Group.user_set.through
_User = get_user_model()
_GROUPS_THROUGH = _User.groups.through


@receiver(post_save, sender=GroupPagePermission)
@receiver(post_delete, sender=GroupPagePermission)
def invalidate_on_group_page_permission_change(sender, instance, **kwargs):
    clear_menu_cache_for_group(instance.group)


@receiver(post_save, sender=PageRoute)
@receiver(post_delete, sender=PageRoute)
def invalidate_on_page_route_change(sender, instance, **kwargs):
    clear_user_menu_cache()


@receiver(m2m_changed, sender=_GROUPS_THROUGH)
def invalidate_on_user_group_change(sender, instance, action, pk_set, **kwargs):
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if isinstance(instance, Group):
        # 反向操作:group.custom_user_groups.add(user) 时 instance 是 Group,pk_set 是用户 pk
        users = _User.objects.filter(pk__in=pk_set or [])
        for user in users:
            clear_user_menu_cache(user)
    else:
        # 正向操作:user.groups.add(group) 时 instance 是 User
        clear_user_menu_cache(instance)
