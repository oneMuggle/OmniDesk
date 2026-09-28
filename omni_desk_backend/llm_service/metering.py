"""LLM 调用计量与预算拦截（方案 5.6）。

- ``usage_scope(user=..., staff_key=...)``：标记这段代码里的 LLM 调用算在谁头上，并累计本轮合计；
- ``iterate_in_scope``：流式生成器每次 ``next()`` 都重新进入 scope（不依赖 contextvar 跨 yield 保持）；
- ``check_before_call(app_name)``：调用前检查当前用户 / 应用是否已到硬上限，到了抛 ``LlmBudgetExceeded``；
- ``record_call``：调用成功或失败后记账（``smart_assistant.budget.usage``）。

记账和检查本身出错时一律放行，只写日志，不影响 LLM 调用。
"""

from __future__ import annotations

import math
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from collections.abc import Iterable, Iterator

from observability import get_logger

logger = get_logger(__name__, "llm_service")

_current: ContextVar[UsageScope | None] = ContextVar("llm_usage_scope", default=None)

_CJK = re.compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")


class LlmBudgetExceeded(Exception):
    """当前用户或应用今日 LLM 额度已用完（硬上限）。"""

    code = "budget_exceeded"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass
class UsageScope:
    user_id: int | None = None
    staff_key: str = ""
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: Decimal = Decimal("0")
    estimated: bool = False
    # 本轮中途被硬上限拦下时的提示(入口据此把通用失败改写成「额度已用完」)
    blocked_message: str = ""

    def add(self, prompt: int, completion: int, total: int, cost: Decimal, estimated: bool) -> None:
        self.calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += total
        self.estimated_cost += cost
        self.estimated = self.estimated or estimated

    def usage_fields(self) -> dict:
        """AgentLog 回填用：本轮所有 LLM 调用的合计；没有调用时全为 None。"""
        if not self.calls:
            return {"input_tokens": None, "output_tokens": None, "total_tokens": None, "estimated_cost": None}
        return {
            "input_tokens": self.prompt_tokens,
            "output_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
        }


def current_scope() -> UsageScope | None:
    return _current.get()


def make_scope(user=None, staff_key: str = "") -> UsageScope:
    """新建计量范围(不进入);配合 ``usage_scope(scope=...)`` / ``iterate_in_scope`` 使用。"""
    user_id = getattr(user, "pk", None) if user is not None and getattr(user, "is_authenticated", False) else None
    return UsageScope(user_id=user_id, staff_key=staff_key or "")


@contextmanager
def usage_scope(user=None, staff_key: str = "", scope: UsageScope | None = None):
    """进入计量范围；``scope`` 传入时复用（例如流式生成器在多次 next 之间共用同一个）。"""
    if scope is None:
        scope = make_scope(user, staff_key)
    token = _current.set(scope)
    try:
        yield scope
    finally:
        _current.reset(token)


def iterate_in_scope(iterable: Iterable, scope: UsageScope) -> Iterator:
    """逐项迭代 ``iterable``，每次取值都在 ``scope`` 内进行；消费方关闭时同样在 scope 内关闭。"""
    iterator = iter(iterable)
    try:
        while True:
            with usage_scope(scope=scope):
                try:
                    item = next(iterator)
                except StopIteration:
                    return
            yield item
    finally:
        close = getattr(iterator, "close", None)
        if close is not None:
            with usage_scope(scope=scope):
                close()


def estimate_tokens(text: str) -> int:
    """没有 usage 时按字数估算：中日韩字符约 0.7 token/字，其他约 4 字符/token。"""
    if not text:
        return 0
    cjk = len(_CJK.findall(text))
    return math.ceil(cjk * 0.7 + (len(text) - cjk) / 4)


def messages_text(messages: list | None) -> str:
    parts = []
    for message in messages or []:
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):  # 多段内容
            parts.extend(str(p.get("text", "")) for p in content if isinstance(p, dict))
    return "\n".join(parts)


def normalize_usage(usage: Any, prompt_text: str, completion_text: str) -> tuple[int, int, int, bool]:
    """返回 ``(prompt, completion, total, estimated)``；usage 缺失或全 0 时按字数估算。"""
    usage = usage if isinstance(usage, dict) else {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or 0) or prompt + completion
    if total > 0:
        return prompt, completion, total, False
    prompt = estimate_tokens(prompt_text)
    completion = estimate_tokens(completion_text)
    return prompt, completion, prompt + completion, True


def record_call(
    app_name: str,
    *,
    usage: Any = None,
    prompt_text: str = "",
    completion_text: str = "",
    cost: Any = None,
    failed: bool = False,
) -> None:
    """记一次调用（失败只记次数）。任何异常只写日志。"""
    scope = current_scope()
    try:
        if failed:
            prompt = completion = total = 0
            estimated = False
            cost_value = Decimal("0")
        else:
            prompt, completion, total, estimated = normalize_usage(usage, prompt_text, completion_text)
            raw_cost = cost
            if raw_cost is None and isinstance(usage, dict):
                raw_cost = usage.get("estimated_cost")
            cost_value = Decimal(str(raw_cost or 0))
            if scope is not None:
                scope.add(prompt, completion, total, cost_value, estimated)
        from smart_assistant.budget.usage import add_usage

        add_usage(
            user_id=scope.user_id if scope else None,
            staff_key=scope.staff_key if scope else "",
            app_name=app_name,
            calls=0 if failed else 1,
            failed_calls=1 if failed else 0,
            estimated_calls=1 if (estimated and not failed) else 0,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            estimated_cost=cost_value,
        )
    except Exception as exc:
        logger.warning("LLM 用量记账失败: app=%s type=%s", app_name, type(exc).__name__)


def check_before_call(app_name: str) -> None:
    """当前用户或应用已到硬上限时抛 ``LlmBudgetExceeded``；检查出错时放行。"""
    scope = current_scope()
    try:
        from smart_assistant.budget.policy import blocked_message

        message = blocked_message(user_id=scope.user_id if scope else None, app_name=app_name)
    except Exception as exc:
        logger.warning("LLM 预算检查失败，放行: app=%s type=%s", app_name, type(exc).__name__)
        return
    if message:
        if scope is not None:
            scope.blocked_message = message
        raise LlmBudgetExceeded(message)
