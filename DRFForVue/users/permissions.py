from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    自定义权限只允许对象的所有者编辑它
    """
    def has_object_permission(self, request, view, obj):
        # 读取权限允许任何请求
        if request.method in permissions.SAFE_METHODS:
            return True

        # 写入权限只允许对象的owner
        return obj.owner == request.user
