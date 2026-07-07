"""智能助手查询范围。

单一事实来源:所有"用户能看多远"的判断都查 resolve_scope()。
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class SmartAssistantScope(Enum):
    """智能助手查询范围"""

    SELF = "self"
    DEPARTMENT = "department"
    GLOBAL = "global"


def resolve_scope(user: Any) -> SmartAssistantScope:
    """从用户身份派生权限范围。

    优先级:GLOBAL(superuser 或 view_global) > DEPARTMENT(view_department) > SELF(默认)。

    参数:
        user: Django User 实例(允许 Mock,需含 is_superuser 与 has_perm 方法)

    返回:
        SmartAssistantScope 枚举值
    """
    if user is None:
        return SmartAssistantScope.SELF
    if user.is_superuser or user.has_perm("smart_assistant.view_global"):
        return SmartAssistantScope.GLOBAL
    if user.has_perm("smart_assistant.view_department"):
        return SmartAssistantScope.DEPARTMENT
    return SmartAssistantScope.SELF