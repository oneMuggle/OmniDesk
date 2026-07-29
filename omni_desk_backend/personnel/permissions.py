"""personnel 行级权限(P0-A)

Contract / Education / WorkExperience / Qualification / FamilyMember 五个子 ViewSet
此前仅 IsAuthenticated,任意认证用户可读写全员档案。本模块补充行级权限:

- has_permission:仅放行认证用户(匿名一律 401)
- has_object_permission:
  - SAFE_METHODS(GET/HEAD/OPTIONS)放行(列表行级过滤由 get_queryset 负责)
  - admin / hr / manager 全量放行
  - 其他用户仅允许访问本人 personnel 名下的数据
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from users.permissions import _log_permission_denied


def is_privileged_user(user) -> bool:
    """判定 admin / hr / manager(项目约定:Admin/Manager 组成员或 superuser)。"""
    if not (user and getattr(user, "is_authenticated", False)):
        return False
    return user.is_superuser or user.groups.filter(name__in=["Admin", "Manager"]).exists()


class IsOwnerOrManagerOrReadOnly(BasePermission):
    """对象级权限:管理员/HR/经理全量可写,普通用户仅可写本人 personnel 名下数据。"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            _log_permission_denied(request, view)
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if is_privileged_user(request.user):
            return True
        personnel = getattr(obj, "personnel", None)
        owner = getattr(personnel, "user_account", None) if personnel is not None else None
        allowed = owner is not None and owner.id == request.user.id
        if not allowed:
            _log_permission_denied(request, view)
        return allowed
