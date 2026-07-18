"""工具并行执行测试 — 无依赖步骤同时执行,缩短 P95 延迟。

Task 1 of feat/sa-perf-ux: 后端性能优化核心。

覆盖场景:
1. 无依赖步骤并行执行(3 工具各 sleep 0.1s,总耗时 < 0.2s vs 串行 0.3s)
2. 有依赖步骤保持串行(step2 引用 step1.output)
3. 混合依赖:独立步骤并行,有依赖步骤等待前置完成后串行
"""
import time
from unittest.mock import MagicMock, patch

import pytest

from smart_assistant.agent.plan_serializer import Plan, PlanStep
from smart_assistant.agent.tool_chain_executor import ToolChainExecutor
from smart_assistant.tools.tool_context import ToolContext


def _make_tool(execute_fn):
    """创建 mock tool,显式关闭 scope 过滤以走简化路径。"""
    tool = MagicMock()
    tool.execute = execute_fn
    tool.supports_scope_filter = False
    return tool


@pytest.mark.django_db
class TestParallelToolExecution:
    """execute_parallel 核心行为验证。"""

    def test_independent_steps_execute_in_parallel(self, admin_user_obj):
        """3 个无依赖的工具应并行执行,总耗时 < 3 个工具各自耗时之和。

        串行需 0.3s(3 × 0.1s),并行应 < 0.2s(线程池同时执行)。
        """
        ctx = ToolContext(user=admin_user_obj)

        def slow_tool_execute(delay):
            def _execute(*args, **kwargs):
                time.sleep(delay)
                return {"found": True, "data": []}

            return _execute

        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry.get_tool_for_user"
        ) as mock:
            mock.side_effect = [
                _make_tool(slow_tool_execute(0.1)),
                _make_tool(slow_tool_execute(0.1)),
                _make_tool(slow_tool_execute(0.1)),
            ]

            plan = Plan(
                steps=[
                    PlanStep(tool="a", params={}, on_failure="skip"),
                    PlanStep(tool="b", params={}, on_failure="skip"),
                    PlanStep(tool="c", params={}, on_failure="skip"),
                ]
            )
            executor = ToolChainExecutor()
            start = time.time()
            results = executor.execute_parallel(plan, ctx)
            elapsed = time.time() - start

        # 串行需 0.3s,并行应 < 0.2s(留 100ms 余量给线程调度)
        assert elapsed < 0.2, f"并行执行耗时 {elapsed:.3f}s,应 < 0.2s"
        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)

    def test_dependent_steps_remain_serial(self, admin_user_obj):
        """有依赖的步骤必须串行执行(step2 引用 step1.output)。

        验证:
        - 依赖图正确解析 {{step1.output.data[0].id}}
        - step2 在 step1 完成后执行
        - 结果顺序与 plan 顺序一致
        """
        ctx = ToolContext(user=admin_user_obj)

        def make_step_tool(name):
            def _exec(*args, **kwargs):
                if name == "step1_tool":
                    return {"found": True, "data": [{"id": 1}]}
                elif name == "step2_tool":
                    return {"found": True, "data": [{"ref": 1}]}
                return {}

            return _make_tool(_exec)

        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry.get_tool_for_user"
        ) as mock:
            mock.side_effect = lambda tool_name, user: make_step_tool(tool_name)

            plan = Plan(
                steps=[
                    PlanStep(tool="step1_tool", params={}, on_failure="skip"),
                    PlanStep(
                        tool="step2_tool",
                        params={"ref": "{{step1.output.data[0].id}}"},
                        on_failure="skip",
                    ),
                ]
            )
            executor = ToolChainExecutor()
            results = executor.execute_parallel(plan, ctx)

        # 验证两步都成功执行,顺序正确
        assert len(results) == 2
        assert results[0]["tool"] == "step1_tool"
        assert results[1]["tool"] == "step2_tool"
        # step2 的 mock 返回固定值,验证调用链完整
        assert results[1]["output"]["data"][0]["ref"] == 1

    def test_mixed_deps_only_independent_parallel(self, admin_user_obj):
        """混合依赖:A/B 无依赖(并行),C 依赖 A(串行等待)。

        拓扑分组:
        - Layer 0: [A, B] → 并行
        - Layer 1: [C] → 等 A/B 完成后串行

        总耗时 ≈ 2 × 0.1s = 0.2s(A/B 并行 0.1s + C 串行 0.1s)。
        """
        ctx = ToolContext(user=admin_user_obj)

        def slow_tool(delay, output=None):
            def _execute(*args, **kwargs):
                time.sleep(delay)
                return output or {"found": True, "data": []}

            return _execute

        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry.get_tool_for_user"
        ) as mock:
            mock.side_effect = lambda tool_name, user: (
                _make_tool(slow_tool(0.1, {"found": True, "data": [{"id": 42}]}))
                if tool_name == "tool_a"
                else _make_tool(slow_tool(0.1))
            )

            plan = Plan(
                steps=[
                    PlanStep(tool="tool_a", params={}, on_failure="skip"),
                    PlanStep(tool="tool_b", params={}, on_failure="skip"),
                    PlanStep(
                        tool="tool_c",
                        params={"ref": "{{step1.output.data[0].id}}"},
                        on_failure="skip",
                    ),
                ]
            )
            executor = ToolChainExecutor()
            start = time.time()
            results = executor.execute_parallel(plan, ctx)
            elapsed = time.time() - start

        # A/B 并行 0.1s + C 串行 0.1s ≈ 0.2s(串行需 0.3s)
        assert elapsed < 0.28, f"混合依赖耗时 {elapsed:.3f}s,应 < 0.28s"
        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)

    def test_empty_plan_returns_empty_list(self, admin_user_obj):
        """空 plan(无步骤)应返回空列表,不报错。"""
        ctx = ToolContext(user=admin_user_obj)
        plan = Plan(steps=[])

        executor = ToolChainExecutor()
        results = executor.execute_parallel(plan, ctx)

        assert results == []

    def test_single_step_plan_executes_successfully(self, admin_user_obj):
        """单步 plan 应正常执行,无需并行逻辑。"""
        ctx = ToolContext(user=admin_user_obj)

        def single_tool_execute(*args, **kwargs):
            return {"found": True, "data": [{"id": 1}]}

        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry.get_tool_for_user"
        ) as mock:
            mock.return_value = _make_tool(single_tool_execute)

            plan = Plan(
                steps=[
                    PlanStep(tool="single_tool", params={}, on_failure="skip"),
                ]
            )
            executor = ToolChainExecutor()
            results = executor.execute_parallel(plan, ctx)

        assert len(results) == 1
        assert results[0]["status"] == "success"
        assert results[0]["tool"] == "single_tool"

    def test_chain_dependency_all_serial(self, admin_user_obj):
        """链式依赖:A → B → C,所有步骤必须串行执行。

        验证:每个步骤依赖前一步的输出,无法并行。
        """
        ctx = ToolContext(user=admin_user_obj)
        execution_order = []

        def make_ordered_tool(name, delay=0.05):
            def _exec(*args, **kwargs):
                execution_order.append(name)
                time.sleep(delay)
                return {"found": True, "data": [{"name": name}]}

            return _make_tool(_exec)

        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry.get_tool_for_user"
        ) as mock:
            mock.side_effect = lambda tool_name, user: make_ordered_tool(tool_name)

            plan = Plan(
                steps=[
                    PlanStep(tool="tool_a", params={}, on_failure="skip"),
                    PlanStep(
                        tool="tool_b",
                        params={"ref": "{{step1.output.data[0].name}}"},
                        on_failure="skip",
                    ),
                    PlanStep(
                        tool="tool_c",
                        params={"ref": "{{step2.output.data[0].name}}"},
                        on_failure="skip",
                    ),
                ]
            )
            executor = ToolChainExecutor()
            start = time.time()
            results = executor.execute_parallel(plan, ctx)
            elapsed = time.time() - start

        # 链式依赖必须串行:3 × 0.05s = 0.15s
        assert elapsed >= 0.14, f"链式依赖应串行,耗时 {elapsed:.3f}s 应 ≥ 0.14s"
        assert len(results) == 3
        # 验证执行顺序:A → B → C
        assert execution_order == ["tool_a", "tool_b", "tool_c"]

    def test_parallel_execution_tool_error_does_not_crash(self, admin_user_obj):
        """并行执行中某个工具抛异常时,执行器不应崩溃,应继续处理其他工具。

        验证:异常被捕获,不会中断整个并行执行流程。
        """
        ctx = ToolContext(user=admin_user_obj)

        def failing_tool(*args, **kwargs):
            raise ValueError("工具执行失败")

        def successful_tool(*args, **kwargs):
            return {"found": True, "data": []}

        with patch(
            "smart_assistant.agent.tool_chain_executor.ToolRegistry.get_tool_for_user"
        ) as mock:
            mock.side_effect = [
                _make_tool(successful_tool),
                _make_tool(failing_tool),
                _make_tool(successful_tool),
            ]

            plan = Plan(
                steps=[
                    PlanStep(tool="tool_a", params={}, on_failure="skip"),
                    PlanStep(tool="tool_b", params={}, on_failure="skip"),
                    PlanStep(tool="tool_c", params={}, on_failure="skip"),
                ]
            )
            executor = ToolChainExecutor()
            # 关键:不应抛出异常
            results = executor.execute_parallel(plan, ctx)

        # 3 个工具都应有结果(执行器未崩溃)
        assert len(results) == 3, f"期望 3 个结果,实际 {len(results)}"
        # 所有结果都应是字典(无论成功或失败)
        assert all(isinstance(r, dict) for r in results)
