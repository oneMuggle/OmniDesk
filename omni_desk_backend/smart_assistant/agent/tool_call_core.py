"""Shared native tool-calling control loop for agent runners."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ToolCallBudgetExhausted(RuntimeError):
    """Raised when a tool-calling round consumes the shared token budget."""


def run_tool_call_loop(
    router: Any,
    *,
    messages: list[dict],
    tools: list[dict],
    max_rounds: int,
    options: dict | None,
    build_messages: Callable[[list[dict]], list[dict]] = lambda value: value,
    on_usage: Callable[[Any], None] | None = None,
    budget_exhausted: Callable[[], bool] | None = None,
    on_tool_calls: Callable[[list[dict], int], tuple[list[dict], Any | None]]
    | None = None,
    copy_messages: bool = True,
) -> tuple[str, dict, list[dict], int, Any | None]:
    """Run shared generation, reinjection, usage and finish semantics."""
    working_messages = list(messages) if copy_messages else messages
    total_usage: dict = {}
    rounds = 0
    check_budget = budget_exhausted or (lambda: False)
    process = on_tool_calls or (lambda _calls, _round: ([], None))

    def generate(choice: str):
        content, usage, tool_calls = router.generate_with_tools(
            messages=build_messages(working_messages),
            tools=tools,
            tool_choice=choice,
            **({"options": options} if options is not None else {}),
        )
        nonlocal total_usage
        total_usage = merge_usage(total_usage, usage)
        if on_usage is not None:
            on_usage(usage)
        if check_budget():
            raise ToolCallBudgetExhausted("token budget exhausted")
        return content or "", tool_calls

    for round_index in range(max(0, max_rounds)):
        content, tool_calls = generate("auto")
        if not tool_calls:
            return content, total_usage, working_messages, rounds, None
        rounds += 1
        tool_messages, early_result = process(tool_calls, round_index)
        if early_result is not None:
            return content, total_usage, working_messages, rounds, early_result
        working_messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        working_messages.extend(tool_messages)

    content, _tool_calls = generate("none")
    return content, total_usage, working_messages, rounds, None


def merge_usage(total: dict, usage: Any) -> dict:
    merged = dict(total)
    if isinstance(usage, dict):
        for key, value in usage.items():
            if isinstance(value, (int, float)) and isinstance(merged.get(key), (int, float)):
                merged[key] += value
            else:
                merged[key] = value
    return merged
