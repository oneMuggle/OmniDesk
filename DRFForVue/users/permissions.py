from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    """检查用户是否为管理员"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or 
            request.user.role == 'admin'
        )

class IsManager(permissions.BasePermission):
    """检查用户是否为经理"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or
            request.user.role == 'admin' or
            request.user.role == 'manager'
        )

class IsAdminOrManager(permissions.BasePermission):
    """检查用户是否为管理员或经理"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or
            request.user.role in ['admin', 'manager']
        )

def has_module_permission(perm_code):
    """工厂函数创建模块权限检查器"""
    class HasModulePermission(permissions.BasePermission):
        def has_permission(self, request, view):
            if not request.user.is_authenticated:
                return False
                
            if request.user.is_superuser:
                return True
                
            return request.user.has_perm(f'users.{perm_code}')
    return HasModulePermission

class IsOwnerOrReadOnly(permissions.BasePermission):
    """自定义权限只允许对象的所有者编辑它"""
    def has_object_permission(self, request, view, obj):
        # 读取权限允许任何请求
        if request.method in permissions.SAFE_METHODS:
            return True

        # 写入权限只允许对象的owner
        return obj.owner == request.user

class HasSpecificPermission(permissions.BasePermission):
    """检查用户是否具有特定权限"""
    def __init__(self, permission_code):
        self.permission_code = permission_code
        
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        if request.user.is_superuser:
            return True
            
        return request.user.has_perm(self.permission_code)

class IsAdminOrReadOnly(permissions.BasePermission):
    """允许管理员用户进行所有操作，其他用户只读访问"""
    def has_permission(self, request, view):
        # 允许安全方法
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # 检查管理员权限
        return request.user.is_authenticated and (
            request.user.is_superuser or 
            request.user.role == 'admin'
        )
