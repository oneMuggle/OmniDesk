"""联培生模块的 DRF 权限类。"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

MANAGER_GROUP = "联培生管理员"
EXPERT_GROUP = "考核专家组"
MENTOR_GROUP = "联培生导师"


class IsJointStudentManager(BasePermission):
    """必须是联培生管理员 Group 成员（写权限）。"""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.groups.filter(name=MANAGER_GROUP).exists()


class IsExpertGroupMember(BasePermission):
    """必须是考核专家组 Group 成员。"""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.groups.filter(name=EXPERT_GROUP).exists()


class IsJointStudentSelfOrManager(BasePermission):
    """联培生自己或联培生管理员。"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.user.groups.filter(name=MANAGER_GROUP).exists():
            return True
        owner = getattr(obj.joint_student.personnel, "user_account", None)
        return owner == request.user


def user_is_mentor(user) -> bool:
    """当前用户是否属于"联培生导师"组。"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.groups.filter(name=MANAGER_GROUP).exists():
        return True
    return user.groups.filter(name=MENTOR_GROUP).exists()
