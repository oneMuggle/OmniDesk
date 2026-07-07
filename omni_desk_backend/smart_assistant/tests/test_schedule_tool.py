"""Tests for ScheduleTool — backward-compatible execute() signature (Task 5).

This suite covers:

1. New ``execute(params, scope, qs)`` signature for the cross-module
   aggregation path. The path returns ``module_label: "排班"`` and a
   ``count`` field so the orchestrator can render a unified summary.

2. Legacy ``execute(query, context)`` signature still works
   (backward compatibility for existing callers such as
   ``TestScheduleTool`` in ``test_tools.py``).

3. ``_scope_self`` filters ``Schedule`` rows to the duty personnel
   bound to the requesting ``CustomUser`` via the
   ``Personnel.user_account`` reverse relation.

4. Default ``_scope_department`` and ``scope=GLOBAL`` behavior.

The ``duty_person__user_account`` lookup is used (NOT ``duty_person__user``)
because ``Personnel`` has no ``user`` FK — ``CustomUser.personnel`` is the
forward relation with ``related_name="user_account"``.
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from smart_assistant.scope import SmartAssistantScope
from smart_assistant.tools.schedule_tool import ScheduleTool
from smart_assistant.tools.tool_context import ToolContext


@pytest.fixture
def tool():
    return ScheduleTool()


@pytest.mark.django_db
def test_new_execute_signature_accepts_scoped_qs(tool, db):
    """新签名 execute(params, scope, qs) 接收已过滤的 qs"""
    from events.models import Schedule
    from personnel.models import Personnel

    User = get_user_model()
    user_alice = User.objects.create(username="alice5")
    user_bob = User.objects.create(username="bob5")
    p1 = Personnel.objects.create(name="Alice")
    p2 = Personnel.objects.create(name="Bob")
    # 绑定 User <-> Personnel(CustomUser.personnel 是 OneToOne,
    # related_name="user_account",故反向查询走 duty_person__user_account=ctx.user)
    user_alice.personnel = p1
    user_alice.save()
    user_bob.personnel = p2
    user_bob.save()

    today = timezone.now().date()
    tomorrow = today + timezone.timedelta(days=1)
    # Schedule.duty_date 是 unique=True,Alice 用今天、Bob 用明天
    Schedule.objects.create(duty_date=today, duty_person=p1)
    Schedule.objects.create(duty_date=tomorrow, duty_person=p2)

    ctx = ToolContext(user=user_alice, scope=SmartAssistantScope.SELF)
    base_qs = tool.build_base_queryset()
    scoped_qs = tool.get_queryset_for_scope(base_qs, ctx)

    result = tool.execute(params={"date": "today"}, scope=SmartAssistantScope.SELF, qs=scoped_qs)
    assert result["found"] is True
    assert result["count"] == 1  # 只 Alice 的
    assert result["module_label"] == "排班"


@pytest.mark.django_db
def test_old_execute_signature_still_works(tool, db):
    """旧签名 execute(query, context) 仍工作(向后兼容)"""
    from events.models import Schedule
    Schedule.objects.create(duty_date=timezone.now().date())
    ctx = ToolContext(user="u")
    result = tool.execute("今天", ctx)
    assert "found" in result


@pytest.mark.django_db
def test_scope_self_filters_to_user(tool, db):
    """_scope_self 只返回 duty_person.user = ctx.user 的记录"""
    from events.models import Schedule
    from personnel.models import Personnel

    User = get_user_model()
    user_a = User.objects.create(username="alice")
    user_b = User.objects.create(username="bob")
    p_a = Personnel.objects.create(name="Alice")
    p_b = Personnel.objects.create(name="Bob")
    # Personnel 无 user 字段;通过 CustomUser.personnel(OneToOne,related_name="user_account")
    # 建立连接,反向查询走 duty_person__user_account=ctx.user
    user_a.personnel = p_a
    user_a.save()
    user_b.personnel = p_b
    user_b.save()
    today = timezone.now().date()
    tomorrow = today + timezone.timedelta(days=1)
    # Schedule.duty_date 是 unique=True,各占一天
    Schedule.objects.create(duty_date=today, duty_person=p_a)
    Schedule.objects.create(duty_date=tomorrow, duty_person=p_b)

    ctx = ToolContext(user=user_a, scope=SmartAssistantScope.SELF)
    base = tool.build_base_queryset()
    scoped = tool._scope_self(base, ctx)

    assert scoped.count() == 1
    assert scoped.first().duty_person == p_a


@pytest.mark.django_db
def test_scope_department_default_returns_all(tool, db):
    """_scope_department 默认实现 = 透传(子类未重写)"""
    ctx = ToolContext(user="u", scope=SmartAssistantScope.DEPARTMENT)
    base = tool.build_base_queryset()
    scoped = tool._scope_department(base, ctx)
    # 默认实现返回 qs 本身
    assert scoped is base or scoped.count() == base.count()


@pytest.mark.django_db
def test_scope_global_returns_full_qs(tool, db):
    """scope=GLOBAL → 不应用 _scope_self/_scope_department,直接返回 base"""
    from events.models import Schedule
    Schedule.objects.create(duty_date=timezone.now().date())

    ctx = ToolContext(user="u", scope=SmartAssistantScope.GLOBAL)
    base = tool.build_base_queryset()
    scoped = tool.get_queryset_for_scope(base, ctx)
    assert scoped.count() == base.count()
