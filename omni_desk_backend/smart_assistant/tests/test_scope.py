import pytest
from unittest.mock import Mock
from smart_assistant.scope import SmartAssistantScope, resolve_scope


def test_self_scope_default_for_plain_user():
    """普通用户默认 SELF 范围"""
    user = Mock(is_superuser=False, has_perm=Mock(return_value=False))
    assert resolve_scope(user) == SmartAssistantScope.SELF


def test_global_scope_for_superuser():
    """superuser 自动 GLOBAL"""
    user = Mock(is_superuser=True, has_perm=Mock(return_value=False))
    assert resolve_scope(user) == SmartAssistantScope.GLOBAL


def test_global_scope_for_global_permission():
    """拥有 smart_assistant.view_global 权限 → GLOBAL"""
    def has_perm(perm):
        return perm == "smart_assistant.view_global"
    user = Mock(is_superuser=False, has_perm=has_perm)
    assert resolve_scope(user) == SmartAssistantScope.GLOBAL


def test_department_scope_for_dept_permission():
    """拥有 smart_assistant.view_department 但无 view_global → DEPARTMENT"""
    def has_perm(perm):
        return perm == "smart_assistant.view_department"
    user = Mock(is_superuser=False, has_perm=has_perm)
    assert resolve_scope(user) == SmartAssistantScope.DEPARTMENT


def test_department_scope_lower_priority_than_global():
    """同时拥有两个权限 → GLOBAL(高优先级覆盖)"""
    user = Mock(is_superuser=False, has_perm=Mock(return_value=True))
    assert resolve_scope(user) == SmartAssistantScope.GLOBAL


def test_scope_enum_values():
    """枚举值字符串稳定(API/缓存 key 用)"""
    assert SmartAssistantScope.SELF.value == "self"
    assert SmartAssistantScope.DEPARTMENT.value == "department"
    assert SmartAssistantScope.GLOBAL.value == "global"


def test_scope_enum_count():
    """枚举成员数 = 3(SELF/DEPARTMENT/GLOBAL)"""
    assert len(list(SmartAssistantScope)) == 3