from rest_framework import permissions


class IsAdminOrManager(permissions.BasePermission):
    """仅 admin 或 manager 角色可写"""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and (
            hasattr(request.user, "role") and request.user.role in ("admin", "manager")
        )
