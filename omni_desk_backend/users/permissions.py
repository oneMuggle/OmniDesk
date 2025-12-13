from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdmin(BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.groups.filter(name='Admin').exists())

class IsManager(BasePermission):
    """
    Allows access only to manager users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.groups.filter(name='Manager').exists()

class IsAdminOrManager(BasePermission):
    """
    Allows access to admin or manager users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.groups.filter(name__in=['Admin', 'Manager']).exists())

class IsAdminOrManagerOrReadOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    Write permissions are only allowed to admin or manager users.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.groups.filter(name__in=['Admin', 'Manager']).exists())

class IsAdminOrReadOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    Write permissions are only allowed to admin users.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.groups.filter(name='Admin').exists())

class HasPermission(BasePermission):
    """
    Allows access only if the user has all the permissions defined in the view.
    A `required_permissions` attribute must be set on the view.
    """
    def has_permission(self, request, view):
        # Check if the view has the required_permissions attribute
        if not hasattr(view, 'required_permissions'):
            # If not defined, default to allowing access
            return True

        required_permissions = getattr(view, 'required_permissions', [])

        # Check if the user has all the required permissions
        for perm in required_permissions:
            if not request.user.has_perm(perm):
                return False
        
        return True