"""Permissions for smart-assistant global audit and configuration endpoints."""

from rest_framework.permissions import BasePermission


class IsSmartAssistantAdmin(BasePermission):
    """Only a superuser or an explicit Admin-group member may access global data.

    ``is_staff`` alone is not an audit role: managers and other staff can have
    admin-site access without being allowed to read all assistant transcripts.
    """

    message = "仅智能助手管理员可以访问。"

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.groups.filter(name="Admin").exists()))
