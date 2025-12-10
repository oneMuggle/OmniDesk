from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsManagerUser(BasePermission):
    """
    Allows access only to manager users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'manager'

class IsProjectOwnerOrAdmin(BasePermission):
    """
    Custom permission to only allow owners of an object or admins to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in SAFE_METHODS:
            return True

        # Write permissions are only allowed to the manager of the project or an admin.
        return obj.manager == request.user or request.user.role == 'admin'