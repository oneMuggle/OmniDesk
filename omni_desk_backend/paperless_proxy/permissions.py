from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


class IsBindingOwnerOrAdmin(permissions.BasePermission):
    """绑定资源:owner 或 admin 可访问"""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.owner_id == request.user.id
