"""Orchestrator 端到端测试(三身份 + 工具 scope 对比)。

Task 11: 验证 ToolContext.from_request 对三种身份(普通员工/部门主管/管理员)
正确派生 scope,并验证 ScheduleTool 在不同 scope 下返回的数据范围。

Brief 侧 bug 修复:
- ``User.objects.create(username="super", is_superuser=True)`` → 改用
  ``User.objects.create_superuser(...)``(Django PermissionsMixin 要求)。
- ``Personnel.objects.create(name=..., user=...)`` → Personnel 无 user 字段,
  改为 ``user.personnel = p; user.save()``(参考 test_schedule_tool.py)。
- ``Schedule.duty_date`` 是 unique=True → 两个 Schedule 改为不同日期。
"""
import pytest
from unittest.mock import patch, Mock
from smart_assistant.scope import SmartAssistantScope
from smart_assistant.tools.tool_context import ToolContext
from smart_assistant.tools.registry import ToolRegistry


def _create_user(username, has_global=False, has_dept=False):
    """构造带权限的 mock user"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    u = User.objects.create(username=username)
    original_has_perm = u.has_perm

    def fake_has_perm(perm):
        if has_global and perm == "smart_assistant.view_global":
            return True
        if has_dept and perm == "smart_assistant.view_department":
            return True
        return original_has_perm(perm)

    u.has_perm = fake_has_perm
    return u


@pytest.mark.django_db
def test_orchestrator_plain_user_gets_self_scope():
    """普通员工:scope=SELF"""
    u = _create_user("alice", has_global=False, has_dept=False)
    from smart_assistant.tools.tool_context import ToolContext
    ctx = ToolContext.from_request(Mock(user=u, request_id=None))
    assert ctx.scope == SmartAssistantScope.SELF


@pytest.mark.django_db
def test_orchestrator_dept_manager_gets_department_scope():
    """部门主管:scope=DEPARTMENT"""
    u = _create_user("bob", has_global=False, has_dept=True)
    from smart_assistant.tools.tool_context import ToolContext
    ctx = ToolContext.from_request(Mock(user=u, request_id=None))
    assert ctx.scope == SmartAssistantScope.DEPARTMENT


@pytest.mark.django_db
def test_orchestrator_admin_gets_global_scope():
    """管理员:scope=GLOBAL"""
    u = _create_user("admin", has_global=True, has_dept=False)
    from smart_assistant.tools.tool_context import ToolContext
    ctx = ToolContext.from_request(Mock(user=u, request_id=None))
    assert ctx.scope == SmartAssistantScope.GLOBAL


@pytest.mark.django_db
def test_orchestrator_superuser_gets_global_scope():
    """superuser:scope=GLOBAL(无需权限)

    Brief 原写法 ``User.objects.create(username="super", is_superuser=True)``
    在 Django PermissionsMixin 下要求 ``password``/``set_password`` 已设置。
    改用 ``create_superuser`` 是 AbstractUser 推荐做法。
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    u = User.objects.create_superuser(
        username="super", password="x", email="super@example.com"
    )
    from smart_assistant.tools.tool_context import ToolContext
    ctx = ToolContext.from_request(Mock(user=u, request_id=None))
    assert ctx.scope == SmartAssistantScope.GLOBAL


@pytest.mark.django_db
def test_tool_filter_differs_by_scope():
    """同一工具,scope=SELF vs GLOBAL 返回不同数据"""
    from events.models import Schedule
    from personnel.models import Personnel
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from smart_assistant.tools.schedule_tool import ScheduleTool

    User = get_user_model()
    u1 = User.objects.create(username="u1")
    u2 = User.objects.create(username="u2")
    # Personnel 无 user 字段,绑定走 CustomUser.personnel(OneToOne, related_name="user_account")
    p1 = Personnel.objects.create(name="P1")
    p2 = Personnel.objects.create(name="P2")
    u1.personnel = p1
    u1.save()
    u2.personnel = p2
    u2.save()

    today = timezone.now().date()
    tomorrow = today + timezone.timedelta(days=1)
    # Schedule.duty_date 是 unique=True,各占一天
    Schedule.objects.create(duty_date=today, duty_person=p1)
    Schedule.objects.create(duty_date=tomorrow, duty_person=p2)

    tool = ScheduleTool()
    base = tool.build_base_queryset()

    ctx_self = ToolContext(user=u1, scope=SmartAssistantScope.SELF)
    scoped_self = tool.get_queryset_for_scope(base, ctx_self)
    # SELF scope:过滤到本人 personnel 的排班
    # 用 qs.count() 而不是 execute()["count"],因为 execute 会再按 target_date=today 二次过滤
    # (Schedule.duty_date 是 unique=True,无法塞同一天的两条)
    assert scoped_self.count() == 1

    ctx_global = ToolContext(user=u1, scope=SmartAssistantScope.GLOBAL)
    scoped_global = tool.get_queryset_for_scope(base, ctx_global)
    # GLOBAL scope:返回全部排班(不应用 _scope_self)
    assert scoped_global.count() == 2

    # 同时验证新签名 execute(params, scope, qs) 可调用且今日 SELF 仅 1 条
    result_self = tool.execute(params={}, scope=SmartAssistantScope.SELF, qs=scoped_self)
    assert result_self["count"] == 1