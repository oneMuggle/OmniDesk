"""ToolChainExecutor 高级测试 — 嵌套 $variable、失败策略、step-level AgentLog。

Task 2 of feat/sa-multi-tool-chain: 升级 executor 支持生产级 plan。

Pre-flight 修正:Plan 2 文档示例代码用 ToolRegistry.get_tool 的 mock 路径,
与现有 ToolRegistry.get_tool_for_user(tool_name, user) 实际签名不一致。
本测试已改用 get_tool_for_user 适配现状。
"""

from unittest.mock import MagicMock, patch

import pytest

from smart_assistant.agent.plan_serializer import Plan, PlanStep
from smart_assistant.agent.tool_chain_executor import (
    ToolChainExecutor,
    _replace_variables,
    _resolve_nested_var,
)
from smart_assistant.tools.tool_context import ToolContext


class TestNestedVariableResolution:
    """{{step1.output.users[0].id}} 嵌套引用解析。"""

    def test_resolve_nested_dict_access(self):
        assert _resolve_nested_var("step1", {"output": {"users": [{"id": 42}]}}, "output.users[0].id") == 42
        assert _resolve_nested_var("step1", {"output": {"summary": "张三周一值班"}}, "output.summary") == "张三周一值班"

    def test_replace_in_params(self):
        params = {"title": "报告: {{step1.output.summary}}", "user_id": "{{step1.output.users[0].id}}"}
        step_results = {"step1": {"output": {"summary": "张三", "users": [{"id": 42}]}}}
        result = _replace_variables(params, step_results)
        assert result["title"] == "报告: 张三"
        assert result["user_id"] == "42"


@pytest.mark.django_db
class TestFailureStrategies:
    """on_failure: skip / retry / fallback 三种策略。"""

    def test_skip_strategy_continues_after_failure(self, admin_user_obj):
        """某步工具不可用,on_failure=skip 时继续后续步骤。"""
        ctx = ToolContext(user=admin_user_obj)
        plan = Plan(
            steps=[
                PlanStep(tool="broken_tool", params={"x": 1}, on_failure="skip"),
                PlanStep(tool="ok_tool", params={"y": 2}, on_failure="skip"),
            ]
        )

        def get_tool_for_user(name, user):
            if name == "broken_tool":
                return None
            mock = MagicMock()
            mock.execute.return_value = {"found": True, "data": []}
            return mock

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as MockReg:
            MockReg.get_tool_for_user.side_effect = get_tool_for_user

            executor = ToolChainExecutor()
            results = executor.execute(plan, ctx)

        assert len(results) == 2
        assert results[0]["status"] == "skipped"
        assert results[1]["status"] == "success"

    def test_retry_strategy_retries_n_times(self, admin_user_obj):
        """retry_count=2 时,首次失败后重试 1 次(总共 2 次 attempt)。"""
        ctx = ToolContext(user=admin_user_obj)
        plan = Plan(
            steps=[
                PlanStep(tool="flaky_tool", params={}, on_failure="retry", retry_count=2),
            ]
        )

        attempt_count = {"n": 0}

        def get_tool_for_user(name, user):
            mock = MagicMock()

            def execute_side(*args, **kwargs):
                attempt_count["n"] += 1
                if attempt_count["n"] < 2:
                    raise RuntimeError("transient error")
                return {"found": True}

            mock.execute.side_effect = execute_side
            return mock

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as MockReg:
            MockReg.get_tool_for_user.side_effect = get_tool_for_user

            executor = ToolChainExecutor()
            results = executor.execute(plan, ctx)

        assert attempt_count["n"] == 2
        assert results[0]["status"] == "success"


@pytest.mark.django_db
class TestStepLevelAgentLog:
    """每步执行应写入 AgentLog,含 tool / params / output / latency。"""

    def test_each_step_writes_agent_log(self, admin_user_obj):
        from smart_assistant.models import AgentLog

        ctx = ToolContext(user=admin_user_obj)
        plan = Plan(
            steps=[
                PlanStep(tool="schedule", params={"query": "张三"}, on_failure="skip"),
                PlanStep(tool="memo", params={"title": "x"}, on_failure="skip"),
            ]
        )

        def get_tool_for_user(name, user):
            mock = MagicMock()
            mock.execute.return_value = {"found": True, "data": ["张三周一"]}
            return mock

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as MockReg:
            MockReg.get_tool_for_user.side_effect = get_tool_for_user

            executor = ToolChainExecutor()
            executor.execute(plan, ctx)

        logs = AgentLog.objects.filter(intent__startswith="chain:")
        assert logs.count() == 2
        first_log = logs.first()
        assert first_log.tool_used in ("schedule", "memo")
        assert first_log.response_time_ms >= 0
