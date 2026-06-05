from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdmin(BasePermission):
    """
    Allows access only to admin users.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or request.user.groups.filter(name="Admin").exists())
        )


class IsManager(BasePermission):
    """
    Allows access only to manager users.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.groups.filter(name="Manager").exists()


class IsAdminOrManager(BasePermission):
    """
    Allows access to admin or manager users.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or request.user.groups.filter(name__in=["Admin", "Manager"]).exists())
        )


class IsAdminOrManagerOrReadOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    Write permissions are only allowed to admin or manager users.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or request.user.groups.filter(name__in=["Admin", "Manager"]).exists())
        )


class IsAdminOrReadOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    Write permissions are only allowed to admin users.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user
            and request.user.is_authenticated
            and (request.user.is_superuser or request.user.groups.filter(name="Admin").exists())
        )


class HasPermission(BasePermission):
    """
    Allows access only if the user has all the permissions defined in the view.
    A `required_permissions` attribute must be set on the view.
    """

    def has_permission(self, request, view):
        # Check if the view has the required_permissions attribute
        if not hasattr(view, "required_permissions"):
            # If not defined, default to allowing access
            return True

        required_permissions = getattr(view, "required_permissions", [])
        if isinstance(required_permissions, str):
            required_permissions = [required_permissions]
        elif not isinstance(required_permissions, list):
            return True  # Not an iterable, so we can't check permissions.

        # Check if the user has all the required permissions
        for perm in required_permissions:
            if not request.user.has_perm(perm):
                return False

        return True


class IsHR(BasePermission):
    """HR 权限:Manager 组 OR superuser。

    P2-2 引入。后续可扩展为"Manager 组 + change_personnel 显式权限",
    但项目目前未给 Manager 组配 permissions,故第一版只检查组成员关系。
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return (
            request.user.is_superuser
            or request.user.groups.filter(name="Manager").exists()
        )


class IsAdminOrManagerOrReadOnly(BasePermission):
    """Admin / HR 可写,其他认证用户只读。

    P2-5 引入。组合 IsAdmin + IsHR 两个权限类(任一通过即可写)。
    GET / HEAD / OPTIONS 一律放行,POST / PUT / PATCH / DELETE 需通过 IsAdmin OR IsHR。
    """

    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

    def has_permission(self, request, view):
        if request.method in self.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        # 写操作:Admin 或 HR
        if not (request.user and request.user.is_authenticated):
            return False
        return IsAdmin().has_permission(request, view) or IsHR().has_permission(request, view)
