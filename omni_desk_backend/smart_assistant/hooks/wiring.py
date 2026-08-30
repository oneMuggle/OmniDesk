"""钩子接线层:内置钩子的生产注册 + 同步执行入口。

生产执行路径(``AgentOrchestrator`` / ``ToolChainExecutor``)是同步代码,
而钩子契约(``hooks/base.py``)是 async 的。本模块桥接两者:

- ``register_builtin_hooks()``:在 ``apps.ready()`` 中调用,把
  ``PiiMaskingHook`` / ``TimeoutGuardHook`` / ``ConfirmationHook`` /
  ``RateLimitHook`` 幂等注册进全局 HookRegistry;
- ``execute_guarded()``:同步工具执行的超时熔断包装(委托
  ``TimeoutGuardHook.run_guarded_sync``,阈值/开关每次动态读 settings);
- ``apply_post_execute_hooks()``:同步驱动 POST_EXECUTE 钩子链
  (PII 脱敏等),失败时降级透传,绝不影响主流程;
- ``apply_failure_hooks()``:同步驱动 ON_FAILURE 钩子链,返回恢复动作。

注册方式与 ``AuditLogHook`` 文档约定的接线一致(``registry.register`` +
``HookEvent``)。区别在于:审计钩子需要按任务实例化(``agent_task_id``),
由多 Agent 执行器自行持有;而 PII / 超时钩子是无状态全局钩子,在应用
启动时一次性挂到全局单例注册表,所有工具执行点共享。
"""

from __future__ import annotations

import asyncio
from typing import Any

from .base import HookEvent, HookRegistry, RecoveryAction, Reject, get_registry

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")


# ---------------------------------------------------------------------------
# 注册点(apps.ready() 调用)
# ---------------------------------------------------------------------------


def register_builtin_hooks(registry: HookRegistry | None = None) -> HookRegistry:
    """把内置钩子注册进全局(或指定)注册表,幂等。

    - ``PiiMaskingHook`` → ``POST_EXECUTE``,priority=5
      (约定先审计后脱敏:审计钩子 priority=10 先跑,拿到原文)
    - ``TimeoutGuardHook`` → ``ON_FAILURE``,priority=10
      (超时异常泄漏到钩子链时提供结构化 fallback 兜底;真正的计时
      由 ``execute_guarded`` 执行包装层完成,见模块级文档)
    - ``ConfirmationHook`` → ``PRE_EXECUTE``,priority=20
      (写工具二次确认,配合前端 confirm-replay 流程)
    - ``RateLimitHook`` → ``PRE_EXECUTE``,priority=25
      (写工具速率限制,P1A-2;优先级高于 ConfirmationHook 是因
      为被限流时不应再触发 draft 缓存,先频次再确认)

    幂等保证:Django ``apps.ready()`` 在测试环境可能被多次调用,按 hook
    ``name`` 去重,避免同一钩子重复挂载导致输出被多次处理。

    Args:
        registry: 目标注册表;None 表示全局单例 ``get_registry()``。

    Returns:
        注册完成后的注册表实例。
    """
    # 延迟导入,避免 hooks.wiring ↔ hooks.builtin 在应用加载期循环
    from .builtin import (
        ConfirmationHook,
        PiiMaskingHook,
        RateLimitHook,
        TimeoutGuardHook,
    )

    reg = registry or get_registry()
    existing_names = {getattr(h, "name", None) for h in reg.list_hooks()}
    if "pii_masking" not in existing_names:
        reg.register(HookEvent.POST_EXECUTE, PiiMaskingHook(), priority=5)
    if "timeout_guard" not in existing_names:
        reg.register(HookEvent.ON_FAILURE, TimeoutGuardHook(), priority=10)
    if "confirmation" not in existing_names:
        reg.register(HookEvent.PRE_EXECUTE, ConfirmationHook(), priority=20)
    if "write_rate_limit" not in existing_names:
        reg.register(HookEvent.PRE_EXECUTE, RateLimitHook(), priority=25)
    return reg


# ---------------------------------------------------------------------------
# 调用点(执行器 / 编排器使用的同步入口)
# ---------------------------------------------------------------------------


def execute_guarded(tool: Any, *args: Any, **kwargs: Any) -> Any:
    """经超时熔断包装执行工具(生产工具执行的统一入口)。

    每次新建 ``TimeoutGuardHook`` 实例:阈值(``SMART_ASSISTANT_TOOL_TIMEOUT``,
    默认 10s)与开关(``SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED``,默认开启)
    在构造时动态读取 settings,支持运行时切换与测试 override。

    - 熔断关闭时:等价于直接调用 ``tool.execute(*args, **kwargs)``;
    - 超时时:立即返回 ``{"found": False, "timed_out": True, ...}`` 失败字典。

    Args:
        tool: 工具实例(需有 ``execute`` 方法与 ``name`` 属性)
        *args / **kwargs: 透传给 ``tool.execute`` 的参数

    Returns:
        工具返回值;超时则为结构化失败字典。
    """
    # 延迟导入,避免 hooks.wiring ↔ hooks.builtin 循环
    from .builtin.timeout_guard import TimeoutGuardHook

    tool_name = getattr(tool, "name", "") or ""
    if not isinstance(tool_name, str):
        # 防御:mock 工具的 name 可能是非字符串属性,仅用于线程命名/日志
        tool_name = ""
    guard = TimeoutGuardHook()
    return guard.run_guarded_sync(tool.execute, *args, tool_name=tool_name, **kwargs)


def _run_coroutine_sync(coro_factory, description: str, fallback: Any) -> Any:
    """在无事件循环的同步上下文中执行钩子协程,失败安全。

    Args:
        coro_factory: 零参函数,每次调用返回一个新协程(重试/跨线程安全)
        description: 日志描述(如 "POST_EXECUTE 钩子链")
        fallback: 任意异常下的降级返回值(原样透传 / ignore 动作)
    """
    try:
        return asyncio.run(coro_factory())
    except RuntimeError:
        # 已处于事件循环中(如 async 上下文嵌套调用同步执行器):
        # asyncio.run 不可用,改在独立线程里起新事件循环执行。
        import concurrent.futures

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro_factory()).result()
        except Exception as exc:  # 钩子失败必须降级,不得影响主流程
            logger.warning("%s执行失败(降级处理): %s", description, exc)
            return fallback
    except Exception as exc:  # 钩子失败必须降级,不得影响主流程
        logger.warning("%s执行失败(降级处理): %s", description, exc)
        return fallback


def apply_post_execute_hooks(tool: Any, result: Any, ctx: Any) -> Any:
    """同步执行全局 POST_EXECUTE 钩子链,返回(可能被修改的)工具结果。

    典型用途:工具输出的统一 PII 脱敏。调用方必须把本函数放在**结果缓存
    之前**,否则缓存命中路径会绕过脱敏。

    失败安全:未注册任何 post 钩子时走快速路径直接返回;钩子链自身异常
    降级为原样返回(与 HookRegistry 内部的吞错策略一致),绝不阻断主流程。
    """
    registry = get_registry()
    if not registry.list_hooks(HookEvent.POST_EXECUTE):
        return result  # 快速路径:无 post 钩子(如注册表被测试重置)
    return _run_coroutine_sync(
        lambda: registry.run_post_hooks(tool, result, ctx),
        "POST_EXECUTE 钩子链",
        result,
    )


def apply_failure_hooks(tool: Any, error: Exception, ctx: Any) -> RecoveryAction:
    """同步执行全局 ON_FAILURE 钩子链,返回恢复动作。

    调用方约定:``action == "fallback"`` 且 ``fallback_value`` 为 dict 时,
    采用钩子提供的结构化兜底结果(如超时熔断失败字典);其余动作
    (ignore / retry / abort)由调用方按自身策略解释,本函数不改变控制流。

    失败安全:无钩子或钩子链异常时返回默认 ``RecoveryAction("ignore")``。
    """
    registry = get_registry()
    default = RecoveryAction(action="ignore")
    if not registry.list_hooks(HookEvent.ON_FAILURE):
        return default
    result = _run_coroutine_sync(
        lambda: registry.run_failure_hooks(tool, error, ctx),
        "ON_FAILURE 钩子链",
        default,
    )
    if isinstance(result, RecoveryAction):
        return result
    return default  # 防御:钩子链返回值类型异常时降级为 ignore


def apply_pre_execute_hooks(tool: Any, ctx: Any, params: dict, excluded_hook_names: set[str] | None = None) -> dict | Reject:
    """同步执行全局 PRE_EXECUTE 钩子链。

    典型用途:``require_confirmation=True`` 的工具在执行前通过钩子返回
    ``Reject(error_code="confirmation_required")`` 挂起执行,等前端二次确认
    后重放;以及输入参数校验、权限预检等场景。

    Args:
        tool: 工具实例(需有 ``name`` 属性,用于钩子内部判定)
        ctx: 工具执行上下文(通常是 ``ToolContext`` 或 ``SharedContext``)
        params: 工具输入参数(可能被多个 Hook 顺序修改)

    Returns:
        dict: 最终参数(可能被多个 Hook 修改)
        Reject: 被某个 Hook 拒绝(通常是 ``require_confirmation=True`` 的工具
        需要前端二次确认,或权限预检失败)

    失败安全:未注册任何 pre 钩子时走快速路径直接返回 params;钩子链自身
    异常降级为原样透传(与 ``apply_post_execute_hooks`` / ``apply_failure_hooks``
    的吞错策略一致),绝不阻断主流程。
    """
    registry = get_registry()
    if not registry.list_hooks(HookEvent.PRE_EXECUTE):
        return params  # 快速路径:无 pre 钩子(如注册表被测试重置)
    result = _run_coroutine_sync(
        lambda: registry.run_pre_hooks(tool, ctx, params, excluded_hook_names=excluded_hook_names),
        "PRE_EXECUTE 钩子链",
        params,  # 异常时降级为原样透传,工具继续执行
    )
    if isinstance(result, (dict, Reject)):
        return result
    return params  # 防御:钩子链返回值类型异常时降级透传
