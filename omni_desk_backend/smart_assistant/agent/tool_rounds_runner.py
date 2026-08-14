"""原生 tool_calls 工具轮(R3-A1 Task 4,从 AgentOrchestrator._run_tool_calls_rounds 提取)。

- 最多 ``settings.MAX_TOOL_CALLS_ROUNDS`` 轮(默认 3);
- 每轮 ``router.generate_with_tools(messages, tools, tool_choice='auto')``;
- 工具错误 4 类:
    * invalid_arguments(JSON 不合法 / schema 校验失败)
    * tool_unavailable_for_user(get_tool_for_user 返回 None)
    * tool_timeout(execute_with_guard 抛 TimeoutError;归类为 execution_failed)
    * execution_failed(任意其他异常)
- 3 轮后强制 ``tool_choice="none"``;
- confirm-replay 工具提前返回 awaiting_confirmation。

内层 ``for tc in tool_calls`` 循环已分解为 ``_process_single_tool_call``
(单 tc 处理,把 4 层嵌套打平成 1 层),confirm-replay 提前返回分支保留在
``run_tool_calls_rounds`` 主循环内(助手无法提前 return 主函数)。
"""

import json
import time

from django.conf import settings

from observability import get_logger

from ..tools.registry import ToolRegistry
from .native_tool_runner import execute_native_tool
from .tool_context_resolver import resolve_tools_for_user  # 保持相对导入正确

logger = get_logger(__name__, "smart_assistant")


def run_tool_calls_rounds(router, *, query, context, llm_messages, json_fallback):
    """原生 tool_calls 工具轮(从 AgentOrchestrator._run_tool_calls_rounds 提取,行为不变)。

    json_fallback: 可调用对象 ``(query, context, llm_messages) -> (content, usage, meta)``,
    用于 generate_with_tools 异常时的 JSON 路径降级。由 orchestrator 传入
    ``self._process_json_path`` 的绑定方法。

    返回 ``(content, usage, meta, tool_round_messages)``:
        content: 最终答案文本(confirm-replay 时为 draft summary;
            JSON 降级时为 JSON 路径答案)
        meta: 含 tool_calls_meta / tool_calls_rounds / tool_call_path,
            confirm-replay 时含 awaiting_confirmation / confirmation_token / draft
        tool_round_messages: 工具结果已 append、未含最终答案轮的
            messages(供流式最终轮复用)
    """
    tools_schema = resolve_tools_for_user(context.user)
    tool_calls_meta = []
    rounds = 0
    max_rounds = int(getattr(settings, "MAX_TOOL_CALLS_ROUNDS", 3))

    for round_idx in range(max_rounds):
        try:
            content, usage, tool_calls = router.generate_with_tools(
                messages=llm_messages, tools=tools_schema, tool_choice="auto"
            )
        except Exception as exc:
            logger.warning("generate_with_tools 异常,降级到 json 路径: %s", exc, exc_info=True)
            content, usage, meta = json_fallback(query=query, context=context, llm_messages=llm_messages)
            return content, usage, meta, llm_messages

        if not tool_calls:
            return (
                content,
                usage,
                {
                    "tool_calls_meta": tool_calls_meta,
                    "tool_calls_rounds": rounds,
                    "tool_call_path": "native",
                },
                llm_messages,
            )

        rounds += 1
        tool_results, tool_calls_meta, confirm_triple = _run_round_tool_calls(
            tool_calls, context, round_idx, tool_calls_meta
        )

        # confirm-replay 提前返回(与移动前行为一致):工具标记需要
        # 用户二次确认 → 立即终止本轮,把 awaiting_confirmation + token 透传
        # 给视图层(前端再带 token 重放执行)。不回灌给 LLM,避免把确认流程
        # 当成工具失败。返回时 llm_messages 不含本轮 assistant/tool 消息。
        if confirm_triple is not None:
            _, _, confirmation, _ = confirm_triple
            draft = confirmation.get("draft") or {}
            return (
                draft.get("summary") or "请确认以下操作",
                {},
                {
                    "tool_calls_meta": tool_calls_meta,
                    "tool_calls_rounds": rounds,
                    "tool_call_path": "native",
                    "awaiting_confirmation": True,
                    "confirmation_token": confirmation["token"],
                    "draft": draft,
                },
                llm_messages,
            )

        # 把 assistant(tool_calls) + tool 结果 append 到 messages
        llm_messages.append(
            {"role": "assistant", "content": content or "", "tool_calls": tool_calls}
        )
        llm_messages.extend(tool_results)

    # 3 轮后兜底:强制 tool_choice="none"
    content, usage, _ = router.generate_with_tools(
        messages=llm_messages, tools=tools_schema, tool_choice="none"
    )
    return (
        content,
        usage,
        {"tool_calls_meta": tool_calls_meta, "tool_calls_rounds": rounds, "tool_call_path": "native"},
        llm_messages,
    )


def _run_round_tool_calls(tool_calls, context, round_idx, tool_calls_meta):
    """执行一轮 tool_calls,收集工具结果 message 与审计条目。

    返回 ``(tool_results, tool_calls_meta, confirm_triple)``:
        confirm_triple: ``None`` 或 ``(tc, result, confirmation, failure)`` ——
            任一工具触发 confirm-replay 时记录并中断本轮(该 tc 的 meta 已
            append,但工具结果不回灌 LLM),由主循环执行提前返回。
    """
    tool_results = []
    confirm_triple = None
    for tc in tool_calls:
        tool_result_msg, meta_entry, confirm_or_none = _process_single_tool_call(
            tc, context, round_idx
        )
        tool_calls_meta.append(meta_entry)
        if confirm_or_none is not None:
            confirm_triple = confirm_or_none
            break
        tool_results.append(tool_result_msg)
    return tool_results, tool_calls_meta, confirm_triple


def _process_single_tool_call(tc, context, round_idx):
    """处理单个 tool_call(从 _run_tool_calls_rounds 内层循环提取,行为不变)。

    工具可用性检查 → 参数解析/schema 校验 → ``execute_native_tool`` →
    失败/确认/成功三分支。把原 4 层嵌套打平成 1 层,是 C901 12→<10 的关键。

    返回 ``(tool_result_msg, meta_entry, confirm_or_none)``:
        tool_result_msg: 该 tc 的工具结果 message(confirm 分支为 None,无回灌)
        meta_entry: 该 tc 的 tool_calls_meta 审计条目
        confirm_or_none: confirm-replay 时返回 ``(tc, result, confirmation, failure)``,
            否则 ``None``
    """
    t0 = time.monotonic()
    func_name = tc.get("function", {}).get("name", "")
    tool_call_id = tc.get("id", "")

    # 1) 工具可用性:required_auth / 匿名用户 / 不存在 → unavailable
    tool = ToolRegistry.get_tool_for_user(func_name, context.user)
    if tool is None:
        return (
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(
                    {"error": "tool_unavailable_for_user"},
                    ensure_ascii=False,
                ),
            },
            {
                "round": round_idx,
                "tool": func_name,
                "error": "unavailable",
                "duration_ms": 0,
            },
            None,
        )

    # 2) 参数解析 + schema 校验
    try:
        raw_args = tc.get("function", {}).get("arguments", "{}")
        if isinstance(raw_args, str):
            args = json.loads(raw_args)
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            args = {}
        validated = tool.validate_arguments(args)
    except Exception as exc:
        return (
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(
                    {"error": "invalid_arguments", "detail": str(exc)},
                    ensure_ascii=False,
                ),
            },
            {
                "round": round_idx,
                "tool": func_name,
                "error": "invalid_args",
                "duration_ms": 0,
            },
            None,
        )

    # 3) 工具执行:统一经 execute_native_tool(scope-aware + 完整 hook 链)。
    # C-1:supports_scope_filter 工具复用 build_base_queryset +
    #      get_queryset_for_scope 分支,确保 SELF/DEPARTMENT/GLOBAL
    #      scope 生效(此前 execute_with_guard 直接跑全量表,跨用户泄漏)。
    # C-2:pre(post/failure hook 链 + confirm-replay 在 helper 内统一处理,
    #      PII 脱敏不再被绕过。
    try:
        result, confirmation, failure = execute_native_tool(tool, validated, context)
    except Exception as exc:
        # helper 内部已收口执行异常;此处兜底防御意外异常
        return (
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(
                    {
                        "error": "execution_failed",
                        "detail": str(exc),
                    },
                    ensure_ascii=False,
                ),
            },
            {
                "round": round_idx,
                "tool": func_name,
                "error": "execution_failed",
                "duration_ms": 0,
            },
            None,
        )

    # 工具执行失败(helper 已 apply_failure_hooks):审计轨迹保留 error 标记
    if failure is not None:
        return (
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(result, ensure_ascii=False),
            },
            {
                "round": round_idx,
                "tool": func_name,
                "error": failure.get("error", "execution_failed"),
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
            None,
        )

    # confirm-replay:工具标记需要用户二次确认 → 记录 confirm_triple,由
    # 主函数执行提前返回(awaiting_confirmation + token 透传视图层)。
    if confirmation is not None:
        return (
            None,
            {
                "round": round_idx,
                "tool": func_name,
                "arguments": validated,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
            (tc, result, confirmation, failure),
        )

    return (
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(result, ensure_ascii=False),
        },
        {
            "round": round_idx,
            "tool": func_name,
            "arguments": validated,
            "duration_ms": int((time.monotonic() - t0) * 1000),
        },
        None,
    )
