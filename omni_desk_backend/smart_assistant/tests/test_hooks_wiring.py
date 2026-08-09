"""钩子生产接线集成测试（修复 1 — HIGH）。

验证 PiiMaskingHook / TimeoutGuardHook 不再只是组件与单测,
而是真正接入生产执行路径:

- 注册点:``apps.ready()`` → ``register_builtin_hooks()`` → 全局 HookRegistry
- 调用点:
    - ``AgentOrchestrator`` 单工具执行(process / process_stream)
    - ``ToolChainExecutor`` 逐步执行(dict 路径 / Plan 路径 / 旧函数版)
  均经 ``execute_guarded``(超时熔断)+ ``apply_post_execute_hooks``(PII 脱敏)

测试矩阵:
- PII:mock 工具返回含手机号/邮箱 → 经 orchestrator / executor 后输出被掩码;
  ``settings.SMART_ASSISTANT_PII_MASKING=False`` 时原样透传(开关生效)
- 超时:慢工具 + 极短 ``SMART_ASSISTANT_TOOL_TIMEOUT`` → 超时失败结构
  (``timed_out=True`` / ``found=False``);
  ``SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED=False`` 时不熔断(开关生效)
- 恢复:ON_FAILURE 钩子给出 fallback 时被执行器采纳
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from smart_assistant.agent.orchestrator import AgentOrchestrator
from smart_assistant.agent.plan_serializer import Plan, PlanStep
from smart_assistant.agent.tool_chain_executor import (
    ToolChainExecutor,
    execute_tool_chain,
)
from smart_assistant.hooks.base import (
    HookEvent,
    RecoveryAction,
    ToolHookBase,
    get_registry,
)
from smart_assistant.hooks.wiring import register_builtin_hooks
from smart_assistant.tools.tool_context import ToolContext


@pytest.fixture(autouse=True)
def _ensure_builtin_hooks():
    """确保全局注册表含内置钩子。

    apps.ready() 在测试进程启动时已注册,但前序测试
    (test_hook_registry.py)可能 ``get_registry(reset=True)`` 重置过单例,
    这里幂等补注册,保证接线测试的前提稳定。
    """
    register_builtin_hooks()
    yield


# ---------------------------------------------------------------------------
# 注册点
# ---------------------------------------------------------------------------


class TestBuiltinHookRegistration:
    def test_apps_ready_registers_builtin_hooks(self):
        """全局注册表包含 pii_masking(POST_EXECUTE)与 timeout_guard(ON_FAILURE)"""
        registry = get_registry()

        post_names = [getattr(h, "name", None) for h in registry.list_hooks(HookEvent.POST_EXECUTE)]
        failure_names = [getattr(h, "name", None) for h in registry.list_hooks(HookEvent.ON_FAILURE)]

        assert "pii_masking" in post_names
        assert "timeout_guard" in failure_names

    def test_register_builtin_hooks_idempotent(self):
        """重复调用 register_builtin_hooks 不会重复挂载同名钩子"""
        register_builtin_hooks()
        register_builtin_hooks()

        registry = get_registry()
        all_names = [getattr(h, "name", None) for h in registry.list_hooks()]

        assert all_names.count("pii_masking") == 1
        assert all_names.count("timeout_guard") == 1


# ---------------------------------------------------------------------------
# orchestrator 单工具路径:PII 脱敏
# ---------------------------------------------------------------------------


class TestOrchestratorPiiWiring:
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.ToolRegistry")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_answer")
    def test_tool_output_masked_before_return(self, mock_generate, mock_classify, mock_registry, mock_plan):
        """mock 工具返回含手机号 → process() 输出被掩码,且缓存的是脱敏结果"""
        mock_plan.return_value = []
        mock_classify.return_value = "personnel_query"
        mock_tool = MagicMock()
        mock_tool.name = "personnel_query"
        mock_tool.require_confirmation = False
        mock_tool.execute.return_value = {
            "found": True,
            "contact": "联系电话 13812345678",
        }
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{"name": "personnel_query", "description": "人员查询"}]
        mock_generate.return_value = ("张三的联系电话已返回。", None)

        result = AgentOrchestrator().process("查张三电话")

        # 手机号被掩码(前 3 后 4)
        assert result["tool_result"]["contact"] == "联系电话 138****5678"
        assert "13812345678" not in json.dumps(result, ensure_ascii=False)

        # 第二次同 query 命中缓存:缓存写入发生在脱敏之后,
        # 故缓存命中路径同样返回脱敏结果,且工具不再被真实调用
        result2 = AgentOrchestrator().process("查张三电话")
        assert result2["tool_result"]["contact"] == "联系电话 138****5678"
        assert mock_tool.execute.call_count == 1

    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.ToolRegistry")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_answer")
    def test_pii_masking_disabled_passthrough(self, mock_generate, mock_classify, mock_registry, mock_plan, settings):
        """SMART_ASSISTANT_PII_MASKING=False 时输出原样透传(开关生效)"""
        settings.SMART_ASSISTANT_PII_MASKING = False
        mock_plan.return_value = []
        mock_classify.return_value = "personnel_query"
        mock_tool = MagicMock()
        mock_tool.name = "personnel_query"
        mock_tool.require_confirmation = False
        mock_tool.execute.return_value = {"found": True, "contact": "13812345678"}
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{"name": "personnel_query", "description": "人员查询"}]
        mock_generate.return_value = ("回答", None)

        result = AgentOrchestrator().process("查张三电话")

        assert result["tool_result"]["contact"] == "13812345678"


# ---------------------------------------------------------------------------
# orchestrator 单工具路径:超时熔断
# ---------------------------------------------------------------------------


class TestOrchestratorTimeoutWiring:
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.ToolRegistry")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_tool_empty_answer")
    def test_slow_tool_times_out(self, mock_empty, mock_classify, mock_registry, mock_plan, settings):
        """慢工具 + 极短阈值 → 立即返回超时失败结构,调用方不挂起"""
        settings.SMART_ASSISTANT_TOOL_TIMEOUT = 0.05
        mock_plan.return_value = []
        mock_classify.return_value = "schedule_query"
        mock_tool = MagicMock()
        mock_tool.name = "schedule_query"
        mock_tool.require_confirmation = False

        def _slow(*args, **kwargs):
            time.sleep(0.3)
            return {"found": True, "schedules": []}

        mock_tool.execute.side_effect = _slow
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{"name": "schedule_query", "description": "排班"}]
        mock_empty.return_value = ("抱歉,暂时无法查询。", None)

        start = time.time()
        result = AgentOrchestrator().process("明天谁值班")
        elapsed = time.time() - start

        # 熔断在 0.05s 附近返回,远小于工具自身的 0.3s
        assert elapsed < 0.25
        assert result["tool_result"]["timed_out"] is True
        assert result["tool_result"]["found"] is False
        # found=False → 走 tool_empty 降级路径
        assert result["tool_fallback"] is True

    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.ToolRegistry")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_answer")
    def test_timeout_disabled_runs_to_completion(
        self, mock_generate, mock_classify, mock_registry, mock_plan, settings
    ):
        """SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED=False 时不熔断(开关生效)"""
        settings.SMART_ASSISTANT_TOOL_TIMEOUT = 0.01
        settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = False
        mock_plan.return_value = []
        mock_classify.return_value = "schedule_query"
        mock_tool = MagicMock()
        mock_tool.name = "schedule_query"
        mock_tool.require_confirmation = False

        def _slow(*args, **kwargs):
            time.sleep(0.1)
            return {"found": True, "schedules": ["张三"]}

        mock_tool.execute.side_effect = _slow
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{"name": "schedule_query", "description": "排班"}]
        mock_generate.return_value = ("明天张三值班。", None)

        result = AgentOrchestrator().process("明天谁值班")

        # 开关关闭 → 慢工具完整执行,不被熔断
        assert result["tool_result"]["found"] is True
        assert result["tool_result"].get("timed_out") is not True


# ---------------------------------------------------------------------------
# ToolChainExecutor 逐步执行:PII 脱敏 + 超时熔断
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExecutorHookWiring:
    def test_dict_path_masks_tool_output(self, admin_user_obj):
        """dict 路径(_execute_single_tool):工具输出邮箱被掩码"""
        ctx = ToolContext(user=admin_user_obj)

        def get_tool_for_user(name, user):
            tool = MagicMock()
            tool.name = name
            tool.supports_scope_filter = False
            tool.execute.return_value = {
                "found": True,
                "message": "联系人邮箱 zhangsan@example.com",
            }
            return tool

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_reg:
            mock_reg.get_tool_for_user.side_effect = get_tool_for_user
            results = ToolChainExecutor().execute(
                {"steps": [{"tool": "personnel_query", "params": {}}]},
                ctx,
            )

        assert len(results) == 1
        assert results[0]["message"] == "联系人邮箱 zha****@example.com"

    def test_plan_path_masks_tool_output(self, admin_user_obj):
        """Plan 路径(_call_tool,_execute_advanced):工具输出手机号被掩码"""
        ctx = ToolContext(user=admin_user_obj)

        def get_tool_for_user(name, user):
            tool = MagicMock()
            tool.name = name
            tool.supports_scope_filter = False
            tool.execute.return_value = {"found": True, "phone": "13912345678"}
            return tool

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_reg:
            mock_reg.get_tool_for_user.side_effect = get_tool_for_user
            plan = Plan(steps=[PlanStep(tool="personnel", params={}, on_failure="skip")])
            results = ToolChainExecutor().execute(plan, ctx)

        assert results[0]["status"] == "success"
        assert results[0]["output"]["phone"] == "139****5678"

    def test_plan_path_slow_tool_times_out(self, admin_user_obj, settings):
        """Plan 路径慢工具 → 超时失败结构(found=False / timed_out=True)"""
        settings.SMART_ASSISTANT_TOOL_TIMEOUT = 0.05
        ctx = ToolContext(user=admin_user_obj)

        def get_tool_for_user(name, user):
            tool = MagicMock()
            tool.name = name
            tool.supports_scope_filter = False

            def _slow(*args, **kwargs):
                time.sleep(0.3)
                return {"found": True}

            tool.execute = _slow
            return tool

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_reg:
            mock_reg.get_tool_for_user.side_effect = get_tool_for_user
            plan = Plan(steps=[PlanStep(tool="slow_tool", params={}, on_failure="skip")])
            start = time.time()
            results = ToolChainExecutor().execute(plan, ctx)
            elapsed = time.time() - start

        assert elapsed < 0.25  # 熔断提前返回,不等满 0.3s
        # 超时是结构化失败字典(非异常)→ step 外层仍为 success 封装
        assert results[0]["output"]["timed_out"] is True
        assert results[0]["output"]["found"] is False
        assert results[0]["output"]["tool"] == "slow_tool"

    def test_plan_path_timeout_disabled(self, admin_user_obj, settings):
        """熔断开关关闭时慢工具完整执行"""
        settings.SMART_ASSISTANT_TOOL_TIMEOUT = 0.01
        settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = False
        ctx = ToolContext(user=admin_user_obj)

        def get_tool_for_user(name, user):
            tool = MagicMock()
            tool.name = name
            tool.supports_scope_filter = False

            def _slow(*args, **kwargs):
                time.sleep(0.1)
                return {"found": True, "data": "done"}

            tool.execute = _slow
            return tool

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_reg:
            mock_reg.get_tool_for_user.side_effect = get_tool_for_user
            plan = Plan(steps=[PlanStep(tool="slow_tool", params={}, on_failure="skip")])
            results = ToolChainExecutor().execute(plan, ctx)

        assert results[0]["status"] == "success"
        assert results[0]["output"]["data"] == "done"

    def test_dict_path_failure_hook_fallback(self, admin_user_obj):
        """ON_FAILURE 钩子给出 fallback 时,异常路径采用其结构化结果"""

        class FallbackHook(ToolHookBase):
            name = "test_fallback_hook"

            async def on_failure(self, tool, error, ctx):
                return RecoveryAction(
                    action="fallback",
                    fallback_value={"found": False, "fallback_marker": True},
                )

        hook = FallbackHook()
        registry = get_registry()
        registry.register(HookEvent.ON_FAILURE, hook, priority=100)  # 高于 timeout_guard
        try:
            ctx = ToolContext(user=admin_user_obj)

            def get_tool_for_user(name, user):
                tool = MagicMock()
                tool.name = name
                tool.supports_scope_filter = False
                tool.execute.side_effect = RuntimeError("工具内部错误")
                return tool

            with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_reg:
                mock_reg.get_tool_for_user.side_effect = get_tool_for_user
                results = ToolChainExecutor().execute(
                    {"steps": [{"tool": "broken", "params": {}}]},
                    ctx,
                )

            assert results[0]["fallback_marker"] is True
            assert results[0]["found"] is False
        finally:
            registry.unregister(hook)

    def test_dict_path_exception_without_fallback_unchanged(self, admin_user_obj):
        """无 fallback 恢复动作时,异常路径保持原 reason="exception" 结构"""
        ctx = ToolContext(user=admin_user_obj)

        def get_tool_for_user(name, user):
            tool = MagicMock()
            tool.name = name
            tool.supports_scope_filter = False
            tool.execute.side_effect = RuntimeError("工具内部错误")
            return tool

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_reg:
            mock_reg.get_tool_for_user.side_effect = get_tool_for_user
            results = ToolChainExecutor().execute(
                {"steps": [{"tool": "broken", "params": {}}]},
                ctx,
            )

        assert results[0]["reason"] == "exception"
        assert "工具内部错误" in results[0]["error"]


# ---------------------------------------------------------------------------
# 旧函数版 execute_tool_chain(orchestrator 无 tool_context 时的降级路径)
# ---------------------------------------------------------------------------


class TestLegacyChainHookWiring:
    def test_legacy_chain_masks_output(self):
        """execute_tool_chain 函数版同样经 POST_EXECUTE 钩子脱敏"""
        tool = MagicMock()
        tool.name = "personnel_query"
        tool.execute.return_value = {"found": True, "phone": "13712345678"}

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_reg:
            mock_reg.get_tool.return_value = tool
            results = execute_tool_chain(
                [{"tool": "personnel_query", "params": {}}],
                "查电话",
            )

        assert results[0]["success"] is True
        assert results[0]["result"]["phone"] == "137****5678"

    def test_legacy_chain_slow_tool_times_out(self, settings):
        """execute_tool_chain 函数版同样受超时熔断保护"""
        settings.SMART_ASSISTANT_TOOL_TIMEOUT = 0.05
        tool = MagicMock()
        tool.name = "slow"

        def _slow(*args, **kwargs):
            time.sleep(0.3)
            return {"found": True}

        tool.execute.side_effect = _slow

        with patch("smart_assistant.agent.tool_chain_executor.ToolRegistry") as mock_reg:
            mock_reg.get_tool.return_value = tool
            start = time.time()
            results = execute_tool_chain([{"tool": "slow", "params": {}}], "q")
            elapsed = time.time() - start

        assert elapsed < 0.25
        assert results[0]["result"]["timed_out"] is True
        assert results[0]["success"] is False
