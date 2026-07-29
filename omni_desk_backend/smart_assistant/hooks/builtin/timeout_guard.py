"""TimeoutGuardHook 超时熔断钩子

借鉴 claw-code 的工具超时控制思路:工具执行超过阈值时**立即返回失败结果**,
而不是让调用方无限挂起。

设计说明
========

现有钩子契约(见 hooks/base.py)::

    async def pre_execute(self, tool, ctx, params) -> dict | Reject
    async def post_execute(self, tool, result, ctx) -> Any
    async def on_failure(self, tool, error, ctx) -> RecoveryAction

``post_execute`` 只能拿到最终 result,**拿不到执行耗时**,因此单靠 post hook
无法实现计时熔断。本模块采用"钩子即配置入口 + 执行包装层做计时"的分工:

- ``TimeoutGuardHook``: 作为**配置入口**与恢复策略提供者。
    - 从 settings ``SMART_ASSISTANT_TOOL_TIMEOUT``(默认 10 秒)读取超时阈值;
    - 从 settings ``SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED``(默认 True)读取开关;
    - ``on_failure`` 中识别超时类异常,返回 ``fallback`` 恢复动作,保证即使
      超时异常泄漏到 HookRegistry 也能得到结构化的兜底结果。
- 执行包装层(``run_guarded`` / ``run_guarded_sync`` 以及
  ``BaseTool.execute_with_guard``): 真正负责计时。
    - 同步路径:把工具函数放进 daemon 线程执行,``join(timeout)`` 到点即返回
      失败字典(调用方不挂起);后台 daemon 线程随函数自然返回而结束,不会
      阻塞解释器退出。Python 无法强杀线程,这是线程方案的固有限制。
    - 异步路径:``asyncio.wait_for`` 包装协程(同步函数则先经
      ``run_in_executor`` 放入线程池),``asyncio.TimeoutError`` 时返回失败字典。

超时失败结果遵循 BaseTool 的 ``found=False`` 约定,便于下游
``validate_result`` / 结果合成器统一识别::

    {
        "found": False,
        "timed_out": True,
        "error": "tool_timeout",
        "message": "工具执行超时(超过 10 秒)",
        "tool": "schedule_query",
    }

Example:
    from smart_assistant.hooks.builtin.timeout_guard import TimeoutGuardHook

    guard = TimeoutGuardHook()  # 读取 settings,默认 10s / 开启

    # 同步包装(用于同步的 BaseTool.execute)
    result = guard.run_guarded_sync(tool.execute, query, context, tool_name=tool.name)

    # 异步包装(用于 async 执行器)
    result = await guard.run_guarded(tool.execute, query, context, tool_name=tool.name)
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import threading
from typing import Any
from collections.abc import Callable

from django.conf import settings

from ..base import RecoveryAction, ToolHookBase

# 默认超时阈值(秒)。settings 未配置 SMART_ASSISTANT_TOOL_TIMEOUT 时生效。
DEFAULT_TOOL_TIMEOUT: float = 10.0

# settings 配置项名称(集中定义,避免散落字符串)
SETTING_TIMEOUT = "SMART_ASSISTANT_TOOL_TIMEOUT"
SETTING_ENABLED = "SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED"


def resolve_timeout(timeout: float | None = None) -> float:
    """解析超时阈值(秒)

    优先级:显式传入 > settings > 默认 10 秒。
    用 getattr 兜底,settings 未定义该项时不报错。
    """
    if timeout is not None:
        return float(timeout)
    return float(getattr(settings, SETTING_TIMEOUT, DEFAULT_TOOL_TIMEOUT))


def resolve_enabled(enabled: bool | None = None) -> bool:
    """解析熔断开关

    优先级:显式传入 > settings > 默认开启(True)。
    """
    if enabled is not None:
        return bool(enabled)
    return bool(getattr(settings, SETTING_ENABLED, True))


def build_timeout_result(tool_name: str, timeout: float) -> dict:
    """构造超时失败结果

    遵循 BaseTool 的 ``found=False`` 约定,额外携带 ``timed_out=True`` 标记,
    便于下游区分"业务未找到"与"执行超时"。
    """
    return {
        "found": False,
        "timed_out": True,
        "error": "tool_timeout",
        "message": f"工具执行超时(超过 {timeout:g} 秒)",
        "tool": tool_name or "unknown",
    }


class TimeoutGuardHook(ToolHookBase):
    """超时熔断 Hook(配置入口 + 恢复策略)

    Attributes:
        name: Hook 名称(固定为 "timeout_guard")
        timeout: 超时阈值(秒),默认读 settings SMART_ASSISTANT_TOOL_TIMEOUT
        enabled: 是否启用熔断,默认读 settings SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED
    """

    name: str = "timeout_guard"

    def __init__(
        self,
        timeout: float | None = None,
        enabled: bool | None = None,
    ) -> None:
        """初始化超时熔断 Hook

        Args:
            timeout: 超时阈值(秒);None 表示从 settings 读取(默认 10 秒)
            enabled: 是否启用;None 表示从 settings 读取(默认 True)
        """
        self.timeout: float = resolve_timeout(timeout)
        self.enabled: bool = resolve_enabled(enabled)

    # ------------------------------------------------------------------
    # 执行包装层(真正的计时逻辑)
    # ------------------------------------------------------------------

    def run_guarded_sync(
        self,
        func: Callable[..., Any],
        *args: Any,
        tool_name: str = "",
        **kwargs: Any,
    ) -> Any:
        """同步执行包装:超过 timeout 立即返回失败字典

        实现方式:daemon 线程 + ``join(timeout)``。到点后主调用立即拿到失败
        结果(不挂起);后台 daemon 线程待 func 自然返回后结束,不会阻塞
        解释器退出。func 内部抛出的异常会原样向上抛出(交由上层
        on_failure 钩子链处理)。

        线程卫生:worker 线程内 Django ORM 打开的 DB 连接是线程私有的,
        func 结束后显式 ``connections.close_all()`` 回收,避免生产路径
        (所有工具执行都经本包装层)的连接泄漏到数据库 idle 超时。

        Args:
            func: 要执行的同步可调用对象(如 ``tool.execute``)
            *args / **kwargs: 透传给 func 的参数
            tool_name: 工具名(仅用于失败结果与日志)

        Returns:
            func 的返回值;超时则返回 ``build_timeout_result`` 失败字典。
            熔断关闭(self.enabled=False)时直接透传执行,不计时。
        """
        if not self.enabled:
            return func(*args, **kwargs)

        # 结果容器:单元素字典比 nonlocal 更直观,且天然线程安全(整体赋值)
        box: dict[str, Any] = {}

        def _target() -> None:
            try:
                box["value"] = func(*args, **kwargs)
            except BaseException as e:
                box["error"] = e
            finally:
                # worker 线程私有 DB 连接的显式回收(见 docstring 线程卫生段)
                try:
                    from django.db import connections

                    connections.close_all()
                except Exception:  # 清理失败不影响结果传递
                    pass

        worker = threading.Thread(
            target=_target,
            name=f"tool-timeout-guard-{tool_name or 'anon'}",
            daemon=True,
        )
        worker.start()
        worker.join(self.timeout)

        if worker.is_alive():
            # 到点未返回 → 熔断。daemon 线程留在后台自行结束。
            return build_timeout_result(tool_name, self.timeout)

        if "error" in box:
            # func 自身异常 → 原样抛出,由上层(钩子链/调用方)决定恢复策略
            raise box["error"]
        return box["value"]

    async def run_guarded(
        self,
        func: Callable[..., Any],
        *args: Any,
        tool_name: str = "",
        **kwargs: Any,
    ) -> Any:
        """异步执行包装:超过 timeout 立即返回失败字典

        - func 是协程函数 → ``asyncio.wait_for`` 直接限时;
        - func 是同步函数 → 先经 ``run_in_executor`` 放入默认线程池,
          再 ``wait_for`` 限时(同步函数阻塞线程池而非事件循环)。

        Args:
            func: 同步或异步可调用对象
            *args / **kwargs: 透传给 func 的参数
            tool_name: 工具名(仅用于失败结果)

        Returns:
            func 的返回值;超时则返回失败字典。熔断关闭时透传执行。
        """
        if not self.enabled:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result

        if inspect.iscoroutinefunction(func):
            awaitable = func(*args, **kwargs)
        else:
            loop = asyncio.get_running_loop()
            awaitable = loop.run_in_executor(
                None,
                functools.partial(func, *args, **kwargs),
            )

        try:
            return await asyncio.wait_for(awaitable, timeout=self.timeout)
        except (asyncio.TimeoutError, TimeoutError):  # noqa: UP041  # Python 3.10 兼容（3.11+ 二者合并）
            return build_timeout_result(tool_name, self.timeout)

    # ------------------------------------------------------------------
    # ToolHook 接口实现
    # ------------------------------------------------------------------

    async def post_execute(self, tool: Any, result: Any, ctx: Any) -> Any:
        """post hook 契约拿不到耗时,此处仅透传(计时由执行包装层完成)"""
        return result

    async def on_failure(self, tool: Any, error: Exception, ctx: Any) -> RecoveryAction:
        """识别超时异常,返回 fallback 恢复动作

        超时异常(内置 TimeoutError,覆盖 asyncio.TimeoutError /
        concurrent.futures.TimeoutError)泄漏到钩子链时,提供结构化的
        兜底失败结果;其他异常交给后续 Hook 处理(ignore)。
        """
        if isinstance(error, TimeoutError):
            tool_name = getattr(tool, "name", "")
            return RecoveryAction(
                action="fallback",
                fallback_value=build_timeout_result(tool_name, self.timeout),
            )
        return RecoveryAction(action="ignore")
