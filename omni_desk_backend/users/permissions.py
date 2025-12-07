from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdmin(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'

class IsManager(BasePermission):
    """
    Allows access only to manager users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'manager'

class IsAdminOrManager(BasePermission):
    """
    Allows access to admin or manager users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.role == 'admin' or request.user.role == 'manager')

class IsAdminOrManagerOrReadOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    Write permissions are only allowed to admin or manager users.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and (request.user.role == 'admin' or request.user.role == 'manager')

class IsAdminOrReadOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    Write permissions are only allowed to admin users.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff