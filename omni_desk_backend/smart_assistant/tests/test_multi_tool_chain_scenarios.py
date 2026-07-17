"""3 个跨工具链场景 E2E — 验证多步 plan 真实跑通。

Task 3 of feat/sa-multi-tool-chain: 演示 LLM 编排能力。

Pre-flight 修正:Plan 2 文档示例代码用 ``ToolRegistry.get_tool`` mock 路径,
与现有 ``ToolRegistry.get_tool_for_user(tool_name, user)`` 实际签名不一致。
本测试已改用 ``get_tool_for_user`` 适配现状。
"""
from unittest.mock import MagicMock, patch

import pytest

from smart_assistant.agent.plan_serializer import Plan, PlanStep
from smart_assistant.agent.tool_chain_executor import ToolChainExecutor
from smart_assistant.tools.tool_context import ToolContext


@pytest.mark.django_db
class TestChainScheduleToMemoToAnnouncement:
    """场景 A: 排班 → 报告(MemoTool) → 公告(AnnouncementTool 只读查询)。"""

    def test_chain_executes_three_tools(self, admin_user_obj):
        schedule_result = {"found": True, "data": [{"date": "周一", "user": "张三"}]}
        memo_result = {"found": True, "data": {"title": "张三排班报告", "content": "周一"}}
        announcement_result = {"found": True, "data": [{"title": "本周公告"}]}

        tool_responses = {
            "schedule": schedule_result,
            "memo": memo_result,
            "announcement": announcement_result,
        }

        def get_tool_for_user(name, user):
            mock = MagicMock()
            mock.execute.return_value = tool_responses.get(name, {"found": False})
            return mock

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as MockReg:
            MockReg.get_tool_for_user.side_effect = get_tool_for_user

            ctx = ToolContext(user=admin_user_obj)
            plan = Plan(steps=[
                PlanStep(tool="schedule", params={"query": "张三这周值班"}, on_failure="skip"),
                PlanStep(
                    tool="memo",
                    params={"title": "{{step1.output.data[0].user}} 排班报告"},
                    on_failure="skip",
                ),
                PlanStep(tool="announcement", params={"query": "最近公告"}, on_failure="skip"),
            ])

            executor = ToolChainExecutor()
            results = executor.execute(plan, ctx)

        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)
        assert "张三" in results[1]["output"]["data"]["title"]


@pytest.mark.django_db
class TestChainSensorToPersonnelToMemo:
    """场景 B: 传感器异常 → 责任人(PersonnelTool) → 周报(MemoTool)。"""

    def test_chain_three_tools_with_dependencies(self, admin_user_obj):
        sensor_result = {"found": True, "data": [{"sensor_id": "S001", "owner": "李四"}]}
        personnel_result = {"found": True, "data": [{"username": "李四", "department": "运维部"}]}
        memo_result = {"found": True, "data": {"title": "周报"}}

        tool_responses = {
            "sensor": sensor_result,
            "personnel": personnel_result,
            "memo": memo_result,
        }

        def get_tool_for_user(name, user):
            mock = MagicMock()
            mock.execute.return_value = tool_responses.get(name, {"found": False})
            return mock

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as MockReg:
            MockReg.get_tool_for_user.side_effect = get_tool_for_user

            ctx = ToolContext(user=admin_user_obj)
            plan = Plan(steps=[
                PlanStep(tool="sensor", params={"query": "本月异常"}, on_failure="skip"),
                PlanStep(
                    tool="personnel",
                    params={"query": "{{step1.output.data[0].owner}}"},
                    on_failure="skip",
                ),
                PlanStep(
                    tool="memo",
                    params={"title": "周报-{{step2.output.data[0].department}}"},
                    on_failure="skip",
                ),
            ])

            executor = ToolChainExecutor()
            results = executor.execute(plan, ctx)

        assert all(r["status"] == "success" for r in results)
        assert results[1]["output"]["data"][0]["username"] == "李四"


@pytest.mark.django_db
class TestChainComplianceToProjectFallback:
    """场景 C: 合规 → 项目 → 失败 fallback(项目工具不可用时降级)。"""

    def test_fallback_strategy_on_project_unavailable(self, admin_user_obj):
        compliance_result = {"found": True, "data": [{"issue_id": "C001"}]}

        def get_tool_for_user(name, user):
            if name == "compliance":
                mock = MagicMock()
                mock.execute.return_value = compliance_result
                return mock
            if name == "project":
                raise ConnectionError("项目服务不可用")
            mock = MagicMock()
            mock.execute.return_value = {"found": False}
            return mock

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as MockReg:
            MockReg.get_tool_for_user.side_effect = get_tool_for_user

            ctx = ToolContext(user=admin_user_obj)
            plan = Plan(steps=[
                PlanStep(tool="compliance", params={"query": "近期合规问题"}, on_failure="skip"),
                PlanStep(tool="project", params={"query": "关联项目"}, on_failure="fallback"),
            ])

            executor = ToolChainExecutor()
            results = executor.execute(plan, ctx)

        assert results[0]["status"] == "success"
        assert results[1]["status"] == "fallback"
        assert "fallback_message" in results[1]["output"]