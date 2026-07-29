"""内置钩子测试:PII 脱敏 / 超时熔断 / 审计 risk_level / 钩子注册

覆盖 hooks/builtin/ 下三个已落地钩子的行为契约:

- PiiMaskingHook(pii_masking.py):
    - 手机号 / 身份证(含末位 X/x)/ 邮箱的掩码格式
    - 多种 PII 混合文本、长数字边界防误报
    - 递归结构(dict/list/tuple)掩码与不可变性
    - 开关:settings SMART_ASSISTANT_PII_MASKING 动态读取与显式参数优先级
- TimeoutGuardHook(timeout_guard.py):
    - 阈值/开关解析优先级(显式 > settings > 默认)
    - 失败结果结构 build_timeout_result
    - run_guarded_sync / run_guarded:超时返回失败字典(调用方不挂起)、
      未超时透传、函数异常原样抛出、熔断关闭透传
    - on_failure:TimeoutError → fallback 兜底;其他异常 → ignore
    - BaseTool.execute_with_guard 胶合层集成
- AuditLogHook(audit_log.py):
    - _audit_input 并入 risk_level 的各分支
    - post_execute / on_failure 写入 AgentLog 时持久化 risk_level
    - 破坏性调用以 WARNING 级别记录
- 注册检查(builtin/__init__.py):
    - 包导出完整、hook name 正确、符合 ToolHook Protocol 且可注册

异步方法统一用 asyncio.run / async_to_sync 以同步测试驱动
(与 test_hook_registry.py / test_audit_event.py 的既有模式一致,
环境未安装 pytest-asyncio)。
"""

import asyncio
import logging
import time
from types import SimpleNamespace

import pytest
from asgiref.sync import async_to_sync

from smart_assistant.hooks.base import HookEvent, HookRegistry, ToolHook
from smart_assistant.hooks.builtin import AuditLogHook, PiiMaskingHook, TimeoutGuardHook
from smart_assistant.hooks.builtin.audit_log import _audit_input
from smart_assistant.hooks.builtin.pii_masking import (
    mask_email,
    mask_id_card,
    mask_phone,
    mask_text,
    mask_value,
)
from smart_assistant.hooks.builtin.timeout_guard import (
    DEFAULT_TOOL_TIMEOUT,
    build_timeout_result,
    resolve_enabled,
    resolve_timeout,
)
from smart_assistant.tools.base import BaseTool

# 慢函数的等待时长与极短阈值:保证超时测试快速(< 0.5s)且时序稳定
SLOW_DELAY = 0.3
SHORT_TIMEOUT = 0.05


# ---------------------------------------------------------------------------
# PII 脱敏:掩码函数格式
# ---------------------------------------------------------------------------


class TestMaskFunctions:
    def test_mask_phone_keeps_first3_last4(self):
        """手机号掩码:前 3 后 4,中间 4 个星号"""
        assert mask_phone("13812345678") == "138****5678"

    def test_mask_id_card_keeps_first6_last4(self):
        """身份证掩码:前 6 后 4,中间 8 个星号(总长保持 18)"""
        masked = mask_id_card("110101199003077758")
        assert masked == "110101********7758"
        assert len(masked) == 18

    def test_mask_email_keeps_local_prefix(self):
        """邮箱掩码:local 保留前 3 位 + 4 星号,域名完整保留"""
        assert mask_email("zhangsan@example.com") == "zha****@example.com"

    def test_mask_email_short_local_keeps_first_char(self):
        """邮箱 local 部分过短(≤2 位)时仅保留第 1 位"""
        assert mask_email("ab@x.com") == "a***@x.com"


# ---------------------------------------------------------------------------
# PII 脱敏:文本级匹配
# ---------------------------------------------------------------------------


class TestMaskText:
    def test_phone_in_text(self):
        assert mask_text("联系电话 13812345678,请尽快回电") == "联系电话 138****5678,请尽快回电"

    def test_id_card_18_digits(self):
        """18 位身份证(数字校验位)被掩码"""
        assert mask_text("身份证号 110101199003077758") == "身份证号 110101********7758"

    def test_id_card_ending_with_upper_x(self):
        """末位大写 X 的身份证被掩码且 X 保留在可见尾段"""
        assert mask_text("证件号:11010119900307775X。") == "证件号:110101********775X。"

    def test_id_card_ending_with_lower_x(self):
        """末位小写 x 的身份证同样被掩码"""
        assert mask_text("11010119900307775x") == "110101********775x"

    def test_email_in_text(self):
        assert mask_text("邮箱 zhangsan@example.com 已登记") == "邮箱 zha****@example.com 已登记"

    def test_mixed_pii_text(self):
        """同一段文本中手机号 + 身份证 + 邮箱全部被掩码"""
        raw = "张三:手机 13812345678,身份证 110101199003077758,邮箱 zhangsan@example.com"
        expected = "张三:手机 138****5678,身份证 110101********7758,邮箱 zha****@example.com"
        assert mask_text(raw) == expected

    def test_long_digit_string_not_masked(self):
        """长数字串(订单号等)不触发手机号/身份证误报:数字边界断言兜底"""
        # 12 位数字:超出手机号 11 位,(?!\d) 断言阻止匹配
        assert mask_text("订单号 138123456789 已发货") == "订单号 138123456789 已发货"
        # 20 位数字:前后均有数字,身份证正则不匹配
        assert mask_text("流水号 12345678901234567890") == "流水号 12345678901234567890"

    def test_plain_text_unchanged(self):
        """无 PII 的普通文本原样返回"""
        text = "今天天气不错,适合值班巡线。"
        assert mask_text(text) == text


# ---------------------------------------------------------------------------
# PII 脱敏:递归结构与不可变性
# ---------------------------------------------------------------------------


class TestMaskValue:
    def test_nested_dict_list_tuple_masked(self):
        """嵌套 dict/list/tuple 中的字符串逐层掩码,标量原样透传"""
        data = {
            "user": {"phone": "13812345678", "email": "lisi@example.com"},
            "records": ["身份证 11010119900307775X", 42, None, True],
            "tags": ("联系人 13900001111",),
            "count": 3,
        }
        masked = mask_value(data)
        assert masked["user"]["phone"] == "138****5678"
        assert masked["user"]["email"] == "lis****@example.com"
        assert masked["records"][0] == "身份证 110101********775X"
        assert masked["records"][1:] == [42, None, True]
        assert masked["tags"] == ("联系人 139****1111",)
        assert masked["count"] == 3

    def test_scalars_pass_through(self):
        """非字符串标量原样返回"""
        for scalar in (42, 3.14, True, None):
            assert mask_value(scalar) is scalar

    def test_input_not_mutated(self):
        """掩码生成新容器,不原地修改入参(项目不可变约定)"""
        original = {"phone": "13812345678", "items": ["ab@x.com"]}
        snapshot = {"phone": "13812345678", "items": ["ab@x.com"]}
        masked = mask_value(original)
        assert original == snapshot  # 入参未被修改
        assert masked != original  # 新容器已掩码


# ---------------------------------------------------------------------------
# PII 脱敏:Hook 行为与开关
# ---------------------------------------------------------------------------


class TestPiiMaskingHook:
    def test_post_execute_masks_result(self):
        """默认启用(post_execute 递归掩码工具输出)"""
        hook = PiiMaskingHook()
        assert hook.enabled is True  # test settings 未定义该项 → getattr 兜底 True
        result = {"found": True, "contact": "13812345678"}
        masked = asyncio.run(hook.post_execute(None, result, None))
        assert masked["contact"] == "138****5678"
        assert masked["found"] is True

    def test_disabled_via_settings_pass_through(self, settings):
        """override settings SMART_ASSISTANT_PII_MASKING=False → 原样透传(同一对象)"""
        settings.SMART_ASSISTANT_PII_MASKING = False
        hook = PiiMaskingHook()  # enabled=None → 每次动态读 settings
        assert hook.enabled is False
        result = {"contact": "13812345678"}
        out = asyncio.run(hook.post_execute(None, result, None))
        assert out is result  # 透传:同一对象,未掩码

    def test_enabled_read_dynamically_from_settings(self, settings):
        """enabled 属性每次从 settings 动态读取(支持运行时切换)"""
        hook = PiiMaskingHook()
        settings.SMART_ASSISTANT_PII_MASKING = False
        assert hook.enabled is False
        settings.SMART_ASSISTANT_PII_MASKING = True
        assert hook.enabled is True

    def test_explicit_enabled_true_overrides_settings(self, settings):
        """显式 enabled=True 优先于 settings=False"""
        settings.SMART_ASSISTANT_PII_MASKING = False
        hook = PiiMaskingHook(enabled=True)
        out = asyncio.run(hook.post_execute(None, {"v": "13812345678"}, None))
        assert out["v"] == "138****5678"

    def test_explicit_enabled_false_overrides_settings(self, settings):
        """显式 enabled=False 优先于 settings=True"""
        settings.SMART_ASSISTANT_PII_MASKING = True
        hook = PiiMaskingHook(enabled=False)
        result = {"v": "13812345678"}
        out = asyncio.run(hook.post_execute(None, result, None))
        assert out is result


# ---------------------------------------------------------------------------
# 超时熔断:阈值/开关解析与失败结果结构
# ---------------------------------------------------------------------------


class TestTimeoutResolution:
    def test_resolve_timeout_explicit_wins(self, settings):
        """显式传入优先于 settings"""
        settings.SMART_ASSISTANT_TOOL_TIMEOUT = 3.0
        assert resolve_timeout(5.5) == 5.5

    def test_resolve_timeout_from_settings(self, settings):
        settings.SMART_ASSISTANT_TOOL_TIMEOUT = 3.0
        assert resolve_timeout() == 3.0

    def test_resolve_timeout_default(self):
        """test settings 未定义该项 → 默认 10 秒"""
        assert resolve_timeout() == DEFAULT_TOOL_TIMEOUT == 10.0

    def test_resolve_enabled_explicit_wins(self, settings):
        settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = True
        assert resolve_enabled(False) is False

    def test_resolve_enabled_from_settings(self, settings):
        settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = False
        assert resolve_enabled() is False

    def test_resolve_enabled_default_true(self):
        assert resolve_enabled() is True


class TestBuildTimeoutResult:
    def test_structure(self):
        """失败字典遵循 found=False 约定并携带 timed_out 标记"""
        assert build_timeout_result("schedule_query", 10.0) == {
            "found": False,
            "timed_out": True,
            "error": "tool_timeout",
            "message": "工具执行超时(超过 10 秒)",
            "tool": "schedule_query",
        }

    def test_empty_tool_name_falls_back_to_unknown(self):
        assert build_timeout_result("", 2.5)["tool"] == "unknown"


class TestTimeoutGuardHookInit:
    def test_reads_settings_at_init(self, settings):
        """构造时从 settings 读取阈值与开关"""
        settings.SMART_ASSISTANT_TOOL_TIMEOUT = 2.5
        settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = False
        hook = TimeoutGuardHook()
        assert hook.timeout == 2.5
        assert hook.enabled is False

    def test_defaults_without_settings(self):
        hook = TimeoutGuardHook()
        assert hook.timeout == DEFAULT_TOOL_TIMEOUT
        assert hook.enabled is True


# ---------------------------------------------------------------------------
# 超时熔断:同步执行包装层
# ---------------------------------------------------------------------------


class TestRunGuardedSync:
    def test_fast_function_passes_through(self):
        """未超时:原样返回函数结果,参数透传"""
        hook = TimeoutGuardHook(timeout=SHORT_TIMEOUT)
        assert hook.run_guarded_sync(lambda x: x * 2, 21) == 42

    def test_timeout_returns_failure_dict_without_blocking(self):
        """超时:立即返回失败字典,调用方不挂起"""
        hook = TimeoutGuardHook(timeout=SHORT_TIMEOUT)
        start = time.monotonic()
        result = hook.run_guarded_sync(time.sleep, SLOW_DELAY, tool_name="slow_tool")
        elapsed = time.monotonic() - start
        assert result["found"] is False
        assert result["timed_out"] is True
        assert result["error"] == "tool_timeout"
        assert result["tool"] == "slow_tool"
        assert elapsed < SLOW_DELAY  # 到点即返回,未等函数跑完

    def test_function_exception_propagates(self):
        """函数自身异常原样抛出(交由上层钩子链处理)"""
        hook = TimeoutGuardHook(timeout=SHORT_TIMEOUT)

        def boom():
            raise ValueError("bang")

        with pytest.raises(ValueError, match="bang"):
            hook.run_guarded_sync(boom)

    def test_disabled_skips_timing(self):
        """熔断关闭:即使超过阈值也透传执行,不返回失败字典"""
        hook = TimeoutGuardHook(timeout=0.01, enabled=False)

        def slow():
            time.sleep(0.1)
            return "done"

        assert hook.run_guarded_sync(slow) == "done"


# ---------------------------------------------------------------------------
# 超时熔断:异步执行包装层
# ---------------------------------------------------------------------------


class TestRunGuardedAsync:
    def test_coroutine_passes_through(self):
        """协程函数未超时:正常透传返回值"""
        hook = TimeoutGuardHook(timeout=SHORT_TIMEOUT)

        async def coro():
            await asyncio.sleep(0.01)
            return "async-ok"

        assert asyncio.run(hook.run_guarded(coro)) == "async-ok"

    def test_coroutine_timeout_returns_failure_dict(self):
        """协程函数超时:返回失败字典"""
        hook = TimeoutGuardHook(timeout=SHORT_TIMEOUT)

        async def slow_coro():
            await asyncio.sleep(SLOW_DELAY)
            return "never"

        result = asyncio.run(hook.run_guarded(slow_coro, tool_name="async_slow"))
        assert result["found"] is False
        assert result["timed_out"] is True
        assert result["tool"] == "async_slow"

    def test_sync_function_runs_in_executor(self):
        """同步函数经 run_in_executor 包装后正常返回"""
        hook = TimeoutGuardHook(timeout=SHORT_TIMEOUT)

        def sync_fast():
            return 42

        assert asyncio.run(hook.run_guarded(sync_fast)) == 42

    def test_sync_function_timeout(self):
        """同步函数超时:同样返回失败字典"""
        hook = TimeoutGuardHook(timeout=SHORT_TIMEOUT)

        def sync_slow():
            time.sleep(SLOW_DELAY)
            return "never"

        result = asyncio.run(hook.run_guarded(sync_slow))
        assert result["timed_out"] is True
        assert result["error"] == "tool_timeout"

    def test_disabled_passes_through_coroutine(self):
        """熔断关闭:协程即使超过阈值也正常返回"""
        hook = TimeoutGuardHook(timeout=0.01, enabled=False)

        async def coro():
            await asyncio.sleep(0.05)
            return "late-but-ok"

        assert asyncio.run(hook.run_guarded(coro)) == "late-but-ok"


# ---------------------------------------------------------------------------
# 超时熔断:ToolHook 接口与 BaseTool 集成
# ---------------------------------------------------------------------------


class TestTimeoutGuardHookInterface:
    def test_post_execute_passes_through(self):
        """post_execute 仅透传(计时由执行包装层完成,钩子拿不到耗时)"""
        hook = TimeoutGuardHook()
        result = {"found": True}
        assert asyncio.run(hook.post_execute(None, result, None)) is result

    def test_on_failure_timeout_returns_fallback(self):
        """超时异常 → fallback 恢复动作,携带结构化兜底失败结果"""
        hook = TimeoutGuardHook(timeout=3.5)
        tool = SimpleNamespace(name="slow_tool")
        action = asyncio.run(hook.on_failure(tool, TimeoutError("timed out"), None))
        assert action.action == "fallback"
        assert action.fallback_value == build_timeout_result("slow_tool", 3.5)
        assert action.fallback_value["timed_out"] is True

    def test_on_failure_other_error_ignored(self):
        """非超时异常 → ignore,交给后续 Hook 处理"""
        hook = TimeoutGuardHook()
        action = asyncio.run(hook.on_failure(SimpleNamespace(name="t"), ValueError("x"), None))
        assert action.action == "ignore"
        assert action.fallback_value is None

    def test_execute_with_guard_integration(self, settings):
        """BaseTool.execute_with_guard 胶合层:读 settings 阈值并熔断"""
        settings.SMART_ASSISTANT_TOOL_TIMEOUT = SHORT_TIMEOUT

        class _SlowTool(BaseTool):
            name = "slow_tool"
            description = "慢工具"
            intent_type = "slow_intent"
            risk_level = "read"

            def execute(self, query, context=None):
                time.sleep(SLOW_DELAY)
                return {"found": True}

        result = _SlowTool().execute_with_guard("查询", None)
        assert result["timed_out"] is True
        assert result["found"] is False
        assert result["tool"] == "slow_tool"


# ---------------------------------------------------------------------------
# 审计钩子:risk_level 并入审计输入
# ---------------------------------------------------------------------------


class TestAuditInputRiskLevel:
    def test_dict_input_merged_with_risk_level(self):
        """ctx.tool_input 为 dict → 追加 risk_level 键(不丢失原键)"""
        ctx = SimpleNamespace(tool_input={"keyword": "张三"})
        tool = SimpleNamespace(name="personnel_query", risk_level="read")
        assert _audit_input(ctx, tool) == {"keyword": "张三", "risk_level": "read"}

    def test_non_dict_input_wrapped(self):
        """ctx.tool_input 非 dict → 包装为 {"params": ..., "risk_level": ...}"""
        ctx = SimpleNamespace(tool_input="raw query")
        tool = SimpleNamespace(risk_level="write")
        assert _audit_input(ctx, tool) == {"params": "raw query", "risk_level": "write"}

    def test_tool_without_risk_level_defaults_to_read(self):
        """工具未声明 risk_level → 兜底 "read"(fail-safe,与 BaseTool 默认值一致)"""
        ctx = SimpleNamespace(tool_input={})
        tool = SimpleNamespace(name="legacy_tool")
        assert _audit_input(ctx, tool)["risk_level"] == "read"

    def test_ctx_without_tool_input(self):
        """ctx 无 tool_input 属性 → 空输入 + risk_level"""
        ctx = SimpleNamespace()
        tool = SimpleNamespace(risk_level="destructive")
        assert _audit_input(ctx, tool) == {"risk_level": "destructive"}


# ---------------------------------------------------------------------------
# 审计钩子:AgentLog 持久化 risk_level
# ---------------------------------------------------------------------------


def _make_ctx(**overrides):
    """构造 AuditLogHook 所需的上下文对象"""
    defaults = {
        "tool_input": {"keyword": "张三"},
        "query": "查询张三",
        "intent": "personnel_query",
        "user": None,
        "session": None,
        "request_id": "req-001",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.django_db
class TestAuditLogRiskLevelPersistence:
    def test_post_execute_persists_risk_level(self):
        """post_execute 写 AgentLog:tool_input 携带工具的 risk_level"""
        from smart_assistant.models import AgentLog

        hook = AuditLogHook()
        tool = SimpleNamespace(name="personnel_query", risk_level="destructive")
        result = {"found": True, "response": "命中 1 条"}

        returned = async_to_sync(hook.post_execute)(tool, result, _make_ctx())

        assert returned == result  # 结果原样透传,不修改
        log = AgentLog.objects.latest("created_at")
        assert log.tool_used == "personnel_query"
        assert log.tool_input == {"keyword": "张三", "risk_level": "destructive"}
        assert log.tool_output == result
        assert log.tool_success is True

    def test_post_execute_read_level_recorded(self):
        """read 级工具的审计记录同样携带 risk_level"""
        from smart_assistant.models import AgentLog

        hook = AuditLogHook()
        tool = SimpleNamespace(name="schedule_query", risk_level="read")

        async_to_sync(hook.post_execute)(tool, {"found": True}, _make_ctx())

        log = AgentLog.objects.latest("created_at")
        assert log.tool_input["risk_level"] == "read"
        assert log.tool_success is True

    def test_on_failure_persists_risk_level(self):
        """失败调用同样记录风险等级(失败的高危调用尤其需要审计)"""
        from smart_assistant.models import AgentLog

        hook = AuditLogHook()
        tool = SimpleNamespace(name="schedule_query", risk_level="write")

        action = async_to_sync(hook.on_failure)(
            tool, RuntimeError("boom"), _make_ctx(tool_input={"q": "x"})
        )

        assert action.action == "ignore"
        log = AgentLog.objects.latest("created_at")
        assert log.tool_success is False
        assert log.tool_input == {"q": "x", "risk_level": "write"}
        assert log.tool_output == {"error": "boom"}

    def test_destructive_call_logs_warning(self, caplog):
        """破坏性工具调用以 WARNING 级别记录,便于运维筛查高危调用"""
        hook = AuditLogHook()
        tool = SimpleNamespace(name="memo_clear", risk_level="destructive")

        with caplog.at_level(logging.WARNING, logger="smart_assistant.hooks.builtin.audit_log"):
            async_to_sync(hook.post_execute)(tool, {"found": True}, _make_ctx())

        assert any("破坏性工具调用" in record.message for record in caplog.records)

    def test_non_destructive_call_no_warning(self, caplog):
        """read 级调用不产生 WARNING(仅 DEBUG,默认级别下无记录)"""
        hook = AuditLogHook()
        tool = SimpleNamespace(name="news_query", risk_level="read")

        with caplog.at_level(logging.WARNING, logger="smart_assistant.hooks.builtin.audit_log"):
            async_to_sync(hook.post_execute)(tool, {"found": True}, _make_ctx())

        assert not any("破坏性工具调用" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# 注册检查:builtin 包导出与 HookRegistry 注册
# ---------------------------------------------------------------------------


class TestHookRegistration:
    def test_builtin_package_exports_all_hooks(self):
        """builtin/__init__ 导出全部三个已落地钩子"""
        from smart_assistant.hooks import builtin

        assert set(builtin.__all__) == {"AuditLogHook", "PiiMaskingHook", "TimeoutGuardHook"}

    def test_hooks_importable_from_builtin_package(self):
        """三个钩子均可从 hooks.builtin 包路径导入"""
        from smart_assistant.hooks.builtin import (  # noqa: F401
            AuditLogHook,
            PiiMaskingHook,
            TimeoutGuardHook,
        )

    def test_hook_names(self):
        """各钩子的 name 属性与注册/审计标识一致"""
        assert PiiMaskingHook().name == "pii_masking"
        assert TimeoutGuardHook().name == "timeout_guard"
        assert AuditLogHook().name == "audit_log"

    def test_builtin_hooks_conform_to_protocol_and_registerable(self):
        """三个钩子均符合 ToolHook Protocol,可注册进 HookRegistry 并被列出"""
        registry = HookRegistry()
        hooks = [PiiMaskingHook(), TimeoutGuardHook(), AuditLogHook()]

        for hook in hooks:
            assert isinstance(hook, ToolHook)  # Protocol 结构检查通过
            registry.register(HookEvent.POST_EXECUTE, hook, priority=5)

        listed = registry.list_hooks(HookEvent.POST_EXECUTE)
        for hook in hooks:
            assert hook in listed

    def test_registry_executes_pii_hook_in_chain(self):
        """集成:PII 钩子注册后,run_post_hooks 链路对工具输出完成掩码"""
        registry = HookRegistry()
        registry.register(HookEvent.POST_EXECUTE, PiiMaskingHook(), priority=5)

        result = {"found": True, "contact": "13812345678"}
        final = asyncio.run(registry.run_post_hooks(None, result, None))
        assert final["contact"] == "138****5678"
