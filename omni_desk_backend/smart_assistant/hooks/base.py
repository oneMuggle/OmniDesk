"""Hook 系统核心定义

提供:
- HookEvent: 三种钩子事件(PRE_EXECUTE / POST_EXECUTE / ON_FAILURE)
- ToolHook: Hook 接口协议(Protocol,支持鸭子类型)
- Reject: pre_execute 拒绝时的返回结构
- RecoveryAction: on_failure 的恢复动作
- HookResult: Hook 执行结果
- HookRegistry: 全局 Hook 注册表(单例,支持优先级排序)
- get_registry(): 获取全局注册表的便捷函数
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Hook 事件类型
# ---------------------------------------------------------------------------


class HookEvent(str, Enum):  # noqa: UP042
    """Hook 触发时机

    - PRE_EXECUTE: 工具执行前,可修改输入或拒绝执行
    - POST_EXECUTE: 工具执行成功后,可修改输出
    - ON_FAILURE: 工具执行失败时,可触发恢复动作
    """

    PRE_EXECUTE = "pre_execute"
    POST_EXECUTE = "post_execute"
    ON_FAILURE = "on_failure"


# ---------------------------------------------------------------------------
# Hook 返回结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Reject:
    """pre_execute 拒绝执行时的返回结构

    Attributes:
        reason: 拒绝原因(用于日志和审计)
        should_abort: True 表示整个任务终止;False 表示跳过当前工具继续
        error_code: 可选的错误码(给前端用)
    """

    reason: str
    should_abort: bool = False
    error_code: str | None = None


@dataclass(frozen=True)
class RecoveryAction:
    """on_failure 的恢复动作

    Attributes:
        action: 恢复策略
            - 'retry': 用新参数重试
            - 'fallback': 用兜底值返回
            - 'abort': 终止当前 subtask
            - 'ignore': 忽略错误,继续下一步
        new_params: retry 时的新工具参数
        fallback_value: fallback 时的兜底返回值
        retry_count: 已重试次数(避免无限循环)
    """

    action: str  # 'retry' / 'fallback' / 'abort' / 'ignore'
    new_params: dict | None = None
    fallback_value: Any = None
    retry_count: int = 0


@dataclass(frozen=True)
class HookResult:
    """Hook 执行结果(用于审计和调试)

    Attributes:
        hook_name: Hook 名称
        event: 触发的事件类型
        outcome: 结果
            - 'allowed': 正常放行
            - 'rejected': 被拒绝
            - 'modified': 输入/输出被修改
            - 'error': Hook 自身出错
        payload: 详细数据(修改后的参数/结果、错误信息等)
    """

    hook_name: str
    event: HookEvent
    outcome: str  # 'allowed' / 'rejected' / 'modified' / 'error'
    payload: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ToolHook 协议
# ---------------------------------------------------------------------------


@runtime_checkable
class ToolHook(Protocol):
    """工具执行钩子接口

    实现者可以只定义需要的方法,其他方法使用默认实现(放行)。
    Protocol + runtime_checkable 允许鸭子类型,不需要显式继承。

    Example:
        class AuditLogHook:
            name = "audit_log"

            async def post_execute(self, tool, result, ctx):
                # 写审计日志
                await AgentLog.objects.create(...)
                return result  # 不修改结果
    """

    name: str

    async def pre_execute(
        self,
        tool: Any,
        ctx: Any,
        params: dict,
    ) -> dict | Reject:
        """工具执行前调用

        Args:
            tool: 即将执行的工具实例(BaseTool)
            ctx: 当前上下文(ToolContext 或 SharedContext)
            params: 工具输入参数

        Returns:
            dict: 修改后的参数(继续执行)
            Reject: 拒绝执行(终止或跳过)

        默认实现: 直接返回原参数(放行)
        """
        return params

    async def post_execute(
        self,
        tool: Any,
        result: Any,
        ctx: Any,
    ) -> Any:
        """工具执行成功后调用

        Args:
            tool: 执行完成的工具实例
            result: 工具返回值
            ctx: 当前上下文

        Returns:
            Any: 修改后的结果(传递给下一个 hook 或返回给调用方)

        默认实现: 直接返回原结果(不修改)
        """
        return result

    async def on_failure(
        self,
        tool: Any,
        error: Exception,
        ctx: Any,
    ) -> RecoveryAction:
        """工具执行失败时调用

        Args:
            tool: 执行失败的工具实例
            error: 抛出的异常
            ctx: 当前上下文

        Returns:
            RecoveryAction: 恢复动作(retry / fallback / abort / ignore)

        默认实现: 忽略错误,继续
        """
        return RecoveryAction(action="ignore")


# ---------------------------------------------------------------------------
# Hook 注册表
# ---------------------------------------------------------------------------


class HookRegistry:
    """全局 Hook 注册表

    支持:
    - 按事件类型注册多个 Hook
    - 按优先级排序(priority 越大越先执行)
    - 顺序执行所有 Hook,前一个的输出作为后一个的输入
    - 任一 Hook 返回 Reject 时立即终止(pre_execute)
    - 自动捕获 Hook 自身的异常,避免影响主流程

    Example:
        registry = HookRegistry()
        registry.register(HookEvent.PRE_EXECUTE, AuditLogHook(), priority=10)
        registry.register(HookEvent.POST_EXECUTE, AuditLogHook(), priority=10)

        # 执行 pre hooks
        final_params = await registry.run_pre_hooks(tool, ctx, params)

        # 执行 post hooks
        final_result = await registry.run_post_hooks(tool, result, ctx)
    """

    def __init__(self) -> None:
        # {event: [(priority, hook), ...]}
        self._hooks: dict[HookEvent, list[tuple[int, ToolHook]]] = {
            event: [] for event in HookEvent
        }
        self._results: list[HookResult] = []  # 最近的执行结果(用于调试)

    def register(
        self,
        event: HookEvent,
        hook: ToolHook,
        priority: int = 0,
    ) -> None:
        """注册 Hook

        Args:
            event: 触发事件
            hook: Hook 实例(需符合 ToolHook Protocol)
            priority: 优先级(越大越先执行,默认 0)

        Raises:
            ValueError: 如果 hook 不符合 ToolHook Protocol
        """
        if not isinstance(hook, ToolHook):
            raise ValueError(f"Hook {hook} 不符合 ToolHook Protocol")

        # 避免重复注册
        for _, existing_hook in self._hooks[event]:
            if existing_hook is hook:
                return

        self._hooks[event].append((priority, hook))
        # 按优先级降序排序(高优先级先执行)
        self._hooks[event].sort(key=lambda x: x[0], reverse=True)

    def unregister(self, hook: ToolHook) -> None:
        """注销 Hook(从所有事件中移除)"""
        for event in HookEvent:
            self._hooks[event] = [
                (p, h) for p, h in self._hooks[event] if h is not hook
            ]

    def list_hooks(self, event: HookEvent | None = None) -> list[ToolHook]:
        """列出已注册的 Hook

        Args:
            event: 指定事件类型;None 表示列出所有

        Returns:
            按优先级排序的 Hook 列表
        """
        if event is not None:
            return [h for _, h in self._hooks[event]]

        # 所有事件的所有 hook(去重)
        seen: set[int] = set()
        result: list[ToolHook] = []
        for hooks in self._hooks.values():
            for _, hook in hooks:
                if id(hook) not in seen:
                    seen.add(id(hook))
                    result.append(hook)
        return result

    async def run_pre_hooks(
        self,
        tool: Any,
        ctx: Any,
        params: dict,
    ) -> dict | Reject:
        """执行所有 PRE_EXECUTE Hook

        按优先级顺序执行,前一个的输出作为后一个的输入。
        任一 Hook 返回 Reject 时立即终止,返回 Reject。

        Returns:
            dict: 最终参数(可能被多个 Hook 修改)
            Reject: 被某个 Hook 拒绝
        """
        current_params = params
        for _, hook in self._hooks[HookEvent.PRE_EXECUTE]:
            try:
                result = await hook.pre_execute(tool, ctx, current_params)
                if isinstance(result, Reject):
                    self._record_result(hook, HookEvent.PRE_EXECUTE, "rejected", {"reason": result.reason})
                    return result
                # 修改参数
                if result != current_params:
                    self._record_result(hook, HookEvent.PRE_EXECUTE, "modified", {"params": result})
                else:
                    self._record_result(hook, HookEvent.PRE_EXECUTE, "allowed")
                current_params = result
            except Exception as e:
                # Hook 自身出错,记录但不影响主流程
                self._record_result(hook, HookEvent.PRE_EXECUTE, "error", {"error": str(e)})
                continue
        return current_params

    async def run_post_hooks(
        self,
        tool: Any,
        result: Any,
        ctx: Any,
    ) -> Any:
        """执行所有 POST_EXECUTE Hook

        按优先级顺序执行,前一个的输出作为后一个的输入。
        所有 Hook 都会执行(即使某个 Hook 出错)。

        Returns:
            Any: 最终结果(可能被多个 Hook 修改)
        """
        current_result = result
        for _, hook in self._hooks[HookEvent.POST_EXECUTE]:
            try:
                new_result = await hook.post_execute(tool, current_result, ctx)
                if new_result != current_result:
                    self._record_result(hook, HookEvent.POST_EXECUTE, "modified")
                else:
                    self._record_result(hook, HookEvent.POST_EXECUTE, "allowed")
                current_result = new_result
            except Exception as e:
                self._record_result(hook, HookEvent.POST_EXECUTE, "error", {"error": str(e)})
                continue
        return current_result

    async def run_failure_hooks(
        self,
        tool: Any,
        error: Exception,
        ctx: Any,
    ) -> RecoveryAction:
        """执行所有 ON_FAILURE Hook

        按优先级顺序执行,返回第一个非 ignore 的 RecoveryAction。
        如果所有 Hook 都返回 ignore,返回默认 RecoveryAction(action='ignore')。

        Returns:
            RecoveryAction: 恢复动作
        """
        for _, hook in self._hooks[HookEvent.ON_FAILURE]:
            try:
                action = await hook.on_failure(tool, error, ctx)
                self._record_result(hook, HookEvent.ON_FAILURE, "allowed", {"action": action.action})
                if action.action != "ignore":
                    return action
            except Exception as e:
                self._record_result(hook, HookEvent.ON_FAILURE, "error", {"error": str(e)})
                continue
        return RecoveryAction(action="ignore")

    def _record_result(
        self,
        hook: ToolHook,
        event: HookEvent,
        outcome: str,
        payload: dict | None = None,
    ) -> None:
        """记录 Hook 执行结果(用于调试)"""
        self._results.append(
            HookResult(
                hook_name=getattr(hook, "name", hook.__class__.__name__),
                event=event,
                outcome=outcome,
                payload=payload or {},
            )
        )
        # 只保留最近 100 条
        if len(self._results) > 100:
            self._results = self._results[-100:]

    def get_recent_results(self, limit: int = 20) -> list[HookResult]:
        """获取最近的 Hook 执行结果(用于调试)"""
        return self._results[-limit:]

    def clear(self) -> None:
        """清空所有 Hook 和结果(主要用于测试)"""
        for event in HookEvent:
            self._hooks[event] = []
        self._results = []


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_REGISTRY: HookRegistry | None = None


def get_registry(reset: bool = False) -> HookRegistry:
    """获取全局 HookRegistry 单例

    Args:
        reset: True 表示重置单例(仅测试用)

    Returns:
        全局 HookRegistry 实例
    """
    global _REGISTRY
    if _REGISTRY is None or reset:
        _REGISTRY = HookRegistry()
    return _REGISTRY


# ---------------------------------------------------------------------------
# ToolHook 基类(具体实现,供继承)
# ---------------------------------------------------------------------------


class ToolHookBase:
    """ToolHook 的基类实现

    提供所有方法的默认实现(放行),子类只需覆盖需要的方法。
    与 ToolHook Protocol 的区别:
    - Protocol 是鸭子类型接口,用于类型检查
    - ToolHookBase 是具体基类,提供默认实现,便于继承

    Example:
        class MyHook(ToolHookBase):
            name = "my_hook"

            async def pre_execute(self, tool, ctx, params):
                # 只覆盖需要的方法
                return {**params, "injected": True}
    """

    name: str = "base_hook"

    async def pre_execute(self, tool: Any, ctx: Any, params: dict) -> dict | Reject:
        """默认放行"""
        return params

    async def post_execute(self, tool: Any, result: Any, ctx: Any) -> Any:
        """默认不修改"""
        return result

    async def on_failure(self, tool: Any, error: Exception, ctx: Any) -> RecoveryAction:
        """默认忽略错误"""
        return RecoveryAction(action="ignore")
