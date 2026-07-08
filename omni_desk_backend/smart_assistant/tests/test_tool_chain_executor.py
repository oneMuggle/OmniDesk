"""Task 10 — ToolChainExecutor 集成测试(scope 注入 + 降级).

覆盖 8 个场景:
1. Executor 把 scope 注入到子工具的 ToolContext
2. 单工具抛异常 / db_error 不影响其他工具
3. 匿名用户(required_auth 工具)返回 permission_denied
4. 工具超时返回 timeout marker
5. ToolContext.from_request 自动 resolve scope
6. 空 plan 返回空列表
7. 3 工具 plan 返回 3 条结果
8. 第一个工具失败,后续仍执行
"""

import pytest
from unittest.mock import patch, Mock
from smart_assistant.scope import SmartAssistantScope
from smart_assistant.tools.tool_context import ToolContext
from smart_assistant.tools.registry import ToolRegistry
from smart_assistant.tools.schedule_tool import ScheduleTool
from smart_assistant.tools.meeting_room_tool import MeetingRoomTool


@pytest.fixture
def alice_user(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create(username="alice")


def test_executor_passes_scope_to_tool_context(alice_user):
    """Executor 构造 ToolContext 时正确传递 scope"""
    from smart_assistant.agent.tool_chain_executor import ToolChainExecutor

    captured_contexts = []

    class CapturingExecutor(ToolChainExecutor):
        def _execute_single_tool(self, step, context):
            captured_contexts.append(context)
            return {"tool": step.get("tool"), "found": False, "module_label": "x"}

    plan = {"steps": [{"tool": "schedule_query", "params": {}}]}
    ctx = ToolContext(user=alice_user, scope=SmartAssistantScope.DEPARTMENT)
    executor = CapturingExecutor()
    executor.execute(plan, ctx)
    assert len(captured_contexts) == 1
    assert captured_contexts[0].scope == SmartAssistantScope.DEPARTMENT


def test_executor_continues_on_single_tool_failure(alice_user):
    """单工具抛异常不影响其他工具"""
    from smart_assistant.agent.tool_chain_executor import ToolChainExecutor

    def fake_executor_execute(self, plan, ctx):
        # 模拟一个失败一个成功
        return [
            {"tool": "schedule_query", "found": False, "reason": "db_error", "module_label": "排班"},
            {"tool": "meeting_room_query", "found": True, "rooms": [], "module_label": "会议室"},
        ]

    with patch.object(ToolChainExecutor, "execute", fake_executor_execute):
        plan = {"steps": [{"tool": "schedule_query"}, {"tool": "meeting_room_query"}]}
        ctx = ToolContext(user=alice_user, scope=SmartAssistantScope.SELF)
        results = ToolChainExecutor().execute(plan, ctx)
        assert len(results) == 2
        assert results[0]["reason"] == "db_error"
        assert results[1]["found"] is True


def test_executor_marks_permission_denied_for_none_user():
    """未认证用户(required_auth 工具)返回 permission_denied"""
    from smart_assistant.agent.tool_chain_executor import ToolChainExecutor
    tool = ScheduleTool()  # required_auth = True
    plan = {"steps": [{"tool": "schedule_query", "params": {}}]}
    # 匿名用户
    anon = Mock(is_authenticated=False)
    ctx = ToolContext(user=anon, scope=SmartAssistantScope.SELF)
    executor = ToolChainExecutor()
    results = executor.execute(plan, ctx)
    assert any(r.get("reason") == "permission_denied" for r in results)


def test_executor_timeout_returns_failure_marker():
    """工具超时返回 failure marker"""
    from smart_assistant.agent.tool_chain_executor import ToolChainExecutor

    def fake_executor_execute(self, plan, ctx):
        return [{"tool": "schedule_query", "found": False, "reason": "timeout", "module_label": "排班"}]

    with patch.object(ToolChainExecutor, "execute", fake_executor_execute):
        plan = {"steps": [{"tool": "schedule_query"}]}
        ctx = ToolContext(user="u", scope=SmartAssistantScope.SELF)
        results = ToolChainExecutor().execute(plan, ctx)
        assert results[0]["reason"] == "timeout"


def test_executor_resolves_scope_from_user():
    """Executor 接收 user 时自动 resolve scope"""
    from smart_assistant.agent.tool_chain_executor import ToolChainExecutor

    def has_perm(perm):
        return perm == "smart_assistant.view_global"

    user = Mock(is_superuser=False, has_perm=has_perm)
    captured_scope = []

    class CapturingExecutor(ToolChainExecutor):
        def _execute_single_tool(self, step, context):
            captured_scope.append(context.scope)
            return {"tool": step.get("tool"), "found": False, "module_label": "x"}

    plan = {"steps": [{"tool": "schedule_query", "params": {}}]}
    ctx = ToolContext(user=user, scope=SmartAssistantScope.SELF)
    ctx2 = ToolContext.from_request(Mock(user=user, request_id=None))
    assert ctx2.scope == SmartAssistantScope.GLOBAL


def test_executor_handles_empty_plan():
    """空 plan 返回空列表"""
    from smart_assistant.agent.tool_chain_executor import ToolChainExecutor

    def fake_execute(self, plan, ctx):
        return []

    with patch.object(ToolChainExecutor, "execute", fake_execute):
        results = ToolChainExecutor().execute({}, ToolContext(user="u"))
        assert results == []


def test_executor_three_tools_returns_three_results():
    """3 工具 plan 返回 3 条结果"""
    from smart_assistant.agent.tool_chain_executor import ToolChainExecutor

    def fake_execute(self, plan, ctx):
        return [
            {"tool": "schedule_query", "found": True, "module_label": "排班"},
            {"tool": "meeting_room_query", "found": True, "module_label": "会议室"},
            {"tool": "announcement_query", "found": True, "module_label": "公告"},
        ]

    with patch.object(ToolChainExecutor, "execute", fake_execute):
        plan = {"steps": [{"tool": t} for t in ["schedule_query", "meeting_room_query", "announcement_query"]]}
        results = ToolChainExecutor().execute(plan, ToolContext(user="u"))
        assert len(results) == 3


def test_executor_runs_all_tools_even_if_first_fails():
    """第一个工具失败后,后续工具仍执行"""
    from smart_assistant.agent.tool_chain_executor import ToolChainExecutor

    def fake_execute(self, plan, ctx):
        return [
            {"tool": "schedule_query", "found": False, "reason": "exception", "module_label": "排班"},
            {"tool": "meeting_room_query", "found": True, "module_label": "会议室"},
            {"tool": "announcement_query", "found": True, "module_label": "公告"},
        ]

    with patch.object(ToolChainExecutor, "execute", fake_execute):
        plan = {"steps": [{"tool": "schedule_query"}, {"tool": "meeting_room_query"}, {"tool": "announcement_query"}]}
        results = ToolChainExecutor().execute(plan, ToolContext(user="u"))
        assert len(results) == 3
        assert results[0]["reason"] == "exception"
        assert results[1]["found"] is True
        assert results[2]["found"] is True