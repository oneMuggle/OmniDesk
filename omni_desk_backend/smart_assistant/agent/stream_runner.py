"""流式编排路径(R3-A1 Task 6,从 AgentOrchestrator.process_stream 提取)。

- ``StreamRunner.stream()`` 等价于原 ``AgentOrchestrator.process_stream``,
  行为零变化;orchestrator 保留同名薄委托。
- 原 C901=30 的主函数分解为多个单职责助手,每个助手 C901 < 10:
  ``_stream_intent`` / ``_stream_cached_answer`` / ``_resolve_native_gate`` /
  ``_stream_native`` / ``_stream_chain`` / ``_stream_single_tool``,以及 C901
  实测驱动的再拆分(``_stream_confirm_or_reject`` / ``_execute_tool_with_cache`` /
  ``_classify_tool_result`` / ``_emit_single_answer`` / ``_emit_native_confirm`` /
  ``_stream_native_final_round``)。
- 经 ``self._orchestrator`` 访问 orchestrator 的实例能力:router /
  ``_endpoint_supports_tool_calls`` / ``_build_initial_messages`` /
  ``_run_tool_calls_rounds`` / ``_process_chain``。
"""

import uuid

from django.conf import settings

from observability import get_logger

from ..tools.registry import ToolRegistry
from ..cache import (
    get_cached_intent,
    cache_intent,
    get_cached_tool_result,
    cache_tool_result,
    get_cached_answer,
    set_confirmation_draft,
    public_confirmation_draft,
    public_tool_calls_meta,
)
from .intent_classifier import (
    classify_intent,
    generate_answer_stream,
    generate_tool_empty_answer,
    generate_general_answer,
)
from .conversation_context import is_failed_answer
from .orchestrator_helpers import _scope_cache_sig
from .tool_chain_planner import generate_tool_chain_plan
from .sse_contract import annotate_error_kind, sse_event
from ..hooks.base import Reject
from ..hooks.wiring import (
    apply_failure_hooks,
    apply_post_execute_hooks,
    apply_pre_execute_hooks,
    execute_guarded,
)

logger = get_logger(__name__, "smart_assistant")


class StreamRunner:
    """流式编排路径(从 AgentOrchestrator.process_stream 提取,行为不变)。

    持有 orchestrator 引用以复用 router / 端点能力检查 / 消息构建 / 链处理。
    """

    def __init__(self, orchestrator):
        self._orchestrator = orchestrator

    def stream(
        self,
        user_query: str,
        conversation_history: list = None,
        tool_context=None,
        use_native_tool_calls: bool | None = None,
    ):
        """流式处理入口:等价于原 AgentOrchestrator.process_stream 的完整行为。"""
        has_history = conversation_history is not None and len(conversation_history) > 0
        scope_sig = _scope_cache_sig(tool_context)
        schemas = ToolRegistry.get_all_schemas()

        # Step 1: 意图分类 + 回答缓存短路(原 1262-1283 行)
        intent = self._stream_intent(user_query, schemas, conversation_history, has_history, scope_sig)
        cached_stream = self._stream_cached_answer(user_query, intent, has_history, scope_sig)
        if cached_stream is not None:
            yield from cached_stream
            return

        # Step 2: 原生 tool_calls 流式分支(原 1285-1322 行)
        if self._resolve_native_gate(tool_context, use_native_tool_calls):
            from smart_assistant.tools.tool_context import ToolContext

            if tool_context is None:
                tool_context = ToolContext(user=None)
            llm_messages = self._orchestrator._build_initial_messages(user_query, tool_context, conversation_history)
            try:
                yield from self._stream_native(user_query, tool_context, llm_messages)
            except Exception as exc:
                logger.warning("原生流式路径异常: %s", exc, exc_info=True)
                yield sse_event({"type": "chunk", "content": f"回答生成失败: {exc}"})
                done = {"type": "done", "finish_reason": "stop", "error": True}
                annotate_error_kind(done, f"回答生成失败: {exc}")
                yield sse_event(done)
            return

        # Step 3: 多工具链(原 1324-1354 行)
        tool_chain = generate_tool_chain_plan(user_query, schemas, conversation_history)
        if tool_chain:
            yield from self._stream_chain(user_query, tool_chain, conversation_history, tool_context)
            return

        # Step 4: 单工具路径(原 1356-1520 行)
        yield from self._stream_single_tool(
            user_query, intent, conversation_history, tool_context, scope_sig, has_history, schemas
        )

    def _stream_intent(self, user_query, schemas, conversation_history, has_history, scope_sig):
        """原 1257-1269 行:意图分类(缓存优先),无历史时算并缓存。"""
        if has_history:
            return None
        cached = get_cached_intent(user_query, schemas, context_sig=scope_sig)
        if cached:
            return cached
        intent = classify_intent(user_query, schemas, conversation_history)
        cache_intent(user_query, schemas, intent, context_sig=scope_sig)
        return intent

    def _stream_cached_answer(self, user_query, intent, has_history, scope_sig):
        """原 1271-1283 行:缓存命中时返回生成器(meta/chunk/done),否则 None。

        注意:仅无历史时检查;返回的生成器在未被消费时无副作用。
        """
        if has_history or intent is None:
            return None
        cached_answer = get_cached_answer(user_query, intent, context_sig=scope_sig, tool_call_path="none")
        if not cached_answer:
            return None

        def _gen():
            yield sse_event({"type": "meta", "intent": intent, "cache_hit": True})
            yield sse_event({"type": "chunk", "content": cached_answer})
            done = {"type": "done", "cache_hit": True, "error": is_failed_answer(cached_answer)}
            if done["error"]:
                annotate_error_kind(done, cached_answer)
            yield sse_event(done)

        return _gen()

    def _resolve_native_gate(self, tool_context, use_native_tool_calls):
        """原 1287-1303 行:原生路径门控(与 process 对称)。"""
        if use_native_tool_calls is not None:
            return bool(use_native_tool_calls)
        try:
            user_is_staff = bool(
                tool_context is not None
                and getattr(tool_context, "user", None) is not None
                and bool(getattr(tool_context.user, "is_staff", False))
            )
            return (
                bool(getattr(settings, "USE_NATIVE_TOOL_CALLS", False))
                and self._orchestrator._endpoint_supports_tool_calls()
                and (user_is_staff or bool(getattr(settings, "USE_NATIVE_TOOL_CALLS_FOR_ALL", False)))
            )
        except Exception:
            logger.warning("原生流式门控检查失败,走 intent 流程", exc_info=True)
            return False

    def _stream_native(self, user_query, tool_context, llm_messages):
        """原 _process_stream_tool_calls_path(第 953-1047 行)整体移入。

        含 confirm-replay 透传 / 无工具轮单 chunk / 有工具轮流式最终轮。
        内部经 ``self._orchestrator.router`` 与 ``self._orchestrator._run_tool_calls_rounds``。
        """
        try:
            content, usage, meta, tool_round_messages = self._orchestrator._run_tool_calls_rounds(
                query=user_query, context=tool_context, llm_messages=llm_messages
            )
        except Exception as exc:
            content = f"回答生成失败: {exc}"
            meta = {"tool_call_path": "native", "tool_calls_rounds": 0}
            tool_round_messages = llm_messages

        # confirm-replay:立即透传给前端,不走最终轮
        if meta.get("awaiting_confirmation"):
            yield from self._emit_native_confirm(meta, content)
            return

        # 输出契约:非确认场景先发 meta(前端依赖首个事件为 meta 渲染意图/工具)。
        tool_calls_meta = meta.get("tool_calls_meta") or []
        tool_used = tool_calls_meta[0].get("tool") if tool_calls_meta and isinstance(tool_calls_meta[0], dict) else None
        yield sse_event(
            {
                "type": "meta",
                "intent": meta.get("intent", "tool_call"),
                "tool_used": tool_used,
                "tool_result": None,
                # L1.1 fix(最终 review):决策日志透传,视图层 AgentLog.create 据此落库
                "tool_call_path": meta.get("tool_call_path", "native"),
                "tool_calls_meta": public_tool_calls_meta(meta.get("tool_calls_meta") or []),
                "tool_calls_rounds": meta.get("tool_calls_rounds") or 0,
            }
        )

        rounds = meta.get("tool_calls_rounds", 0)
        if rounds > 0:
            # 流式最终轮:重生成(真打字动画)。tool_round_messages 以工具结果
            # 收尾,LLM 基于工具结果产出最终自然语言答案。
            full_answer = yield from self._stream_native_final_round(tool_round_messages, content)
        else:
            # 首轮即无 tool_calls / JSON 降级:直接输出缓冲 content 单 chunk
            full_answer = content or ""
            yield sse_event({"type": "chunk", "content": full_answer})

        done = {"type": "done", "finish_reason": "stop", "error": is_failed_answer(full_answer)}
        if done["error"]:
            annotate_error_kind(done, full_answer)
        yield sse_event(done)

    def _emit_native_confirm(self, meta, content):
        """原 confirm-replay 透传段(原生路径):meta + confirmation + done。"""
        tool_calls_meta = meta.get("tool_calls_meta", [])
        tool_used = tool_calls_meta[-1].get("tool", "") if tool_calls_meta else ""
        draft = meta.get("draft", {})
        public_draft = public_confirmation_draft(draft, tool_used)
        yield sse_event(
            {
                "type": "meta",
                "intent": "tool_call",
                "tool_used": tool_used,
                "tool_result": {"draft": public_draft},
                # L1.1 fix(最终 review):决策日志透传,视图层 AgentLog.create 据此落库
                # (spec §3.2 步骤 6 承诺 tool_call_path/tool_calls_meta/tool_calls_rounds)
                "tool_call_path": meta.get("tool_call_path", "native"),
                "tool_calls_meta": public_tool_calls_meta(meta.get("tool_calls_meta") or []),
                "tool_calls_rounds": meta.get("tool_calls_rounds") or 0,
            }
        )
        yield sse_event(
            {
                "type": "confirmation",
                "awaiting_confirmation": True,
                "confirmation_token": meta["confirmation_token"],
                "draft": public_draft,
                "answer": content or "请确认以下操作",
            }
        )
        yield sse_event({"type": "done", "error": False, "awaiting_confirmation": True})

    def _stream_native_final_round(self, tool_round_messages, content):
        """原 rounds>0 分支:流式最终轮(真打字动画)。返回完整答案。"""
        stream_parts = []
        try:
            stream = self._orchestrator.router.generate(messages=tool_round_messages, stream=True)
            for chunk in stream:
                stream_parts.append(chunk)
                yield sse_event({"type": "chunk", "content": chunk})
        except Exception as exc:
            stream_parts = [content or f"回答生成失败: {exc}"]
            yield sse_event({"type": "chunk", "content": stream_parts[0]})
        return "".join(stream_parts)

    def _stream_chain(self, user_query, tool_chain, conversation_history, tool_context):
        """原 1328-1354 行:多工具链聚合结果 → meta/chunk/done 事件。"""
        chain_result = self._orchestrator._process_chain(user_query, tool_chain, conversation_history, tool_context)
        # 1) 发送元数据(meta),含 moduleCounts 等供 AggregatedDayCard 渲染
        yield sse_event(
            {
                "type": "meta",
                "intent": chain_result["intent"],
                "tool_used": chain_result.get("tool_used"),
                "tool_result": chain_result.get("tool_result"),
                "sources": chain_result.get("sources"),
                "tool_fallback": False,
            }
        )
        # 2) 发送单一内容 chunk(_process_chain 已是最终聚合 answer)
        yield sse_event({"type": "chunk", "content": chain_result["answer"]})
        # 3) 结束信号(携带错误标记,供 view 层决定是否落库)
        done = {"type": "done", "error": is_failed_answer(chain_result["answer"])}
        if done["error"]:
            annotate_error_kind(
                done,
                chain_result["answer"],
                tool_used=chain_result.get("tool_used"),
                tool_result=chain_result.get("tool_result"),
            )
        yield sse_event(done)

    def _stream_single_tool(
        self, user_query, intent, conversation_history, tool_context, scope_sig, has_history, schemas
    ):
        """原 1356-1520 行:单工具确认拦截 + 执行 + 流式生成 + done。

        ``rate_limit_error`` 在本方法内声明并使用(不跨助手传递),与移动前一致。
        """
        # P1A-2:RateLimitHook 拦截后,捕获 error_code/retry_after 注入 done 事件,
        # 供视图层 stream() 透传给前端。None = 未触发限流(与移动前行为一致)。
        rate_limit_error = None

        # Step 2 前的意图分类:has_history=True 时(或缓存短路未计算时)需计算
        if intent is None:
            intent = classify_intent(user_query, schemas, conversation_history)

        # Step 2: 工具路由
        tool = ToolRegistry.get_tool(intent)
        tool_result = None
        tool_name = None
        sources = None
        tool_fallback = False

        if tool:
            # === confirm-replay 流式拦截(与 process() 对称) ===
            events, should_return = self._stream_confirm_or_reject(
                tool, user_query, intent, conversation_history, tool_context, scope_sig
            )
            if should_return:
                if events:
                    yield from events
                return
            # 工具执行:结果缓存优先,否则执行 + hook 链 + 缓存回写
            tool_result, tool_name, sources, tool_fallback = self._execute_tool_with_cache(
                tool, user_query, conversation_history, tool_context, scope_sig
            )

        # 先发送元数据
        yield sse_event(
            {
                "type": "meta",
                "intent": intent,
                "tool_used": tool_name,
                "tool_result": tool_result,
                "sources": sources,
                "tool_fallback": tool_fallback,
            }
        )

        # Step 3: 流式生成回答(逐 chunk 发送,返回完整答案供 done 判定)
        full_answer = yield from self._emit_single_answer(
            user_query, intent, tool_name, tool_result, tool_fallback, tool, conversation_history
        )

        # 发送结束信号(携带错误标记,供 view 层决定是否落库;
        # finish_reason 供前端判定回答正常收尾)
        done = {"type": "done", "finish_reason": "stop", "error": is_failed_answer(full_answer)}
        if done["error"]:
            annotate_error_kind(done, full_answer, tool_used=tool_name, tool_result=tool_result)
            # P1A-2:限流被拒时,把 Reject 字段挂到 done 事件;
            # 若触发限流但 LLM 最终仍产出"失败回答",answer 覆盖为限流文案。
            if rate_limit_error:
                done["error_code"] = rate_limit_error["error_code"]
                done["retry_after"] = rate_limit_error["retry_after"]
        yield sse_event(done)

    def _stream_confirm_or_reject(self, tool, user_query, intent, conversation_history, tool_context, scope_sig):
        """原 confirm-replay 流式拦截段(与 process() 对称)。

        返回 ``(events, should_return)``:
            events: 需 yield 的事件列表(拦截未命中时为 None)
            should_return: True 表示主函数应 ``yield from events`` 并立即 return
        """
        if not getattr(tool, "require_confirmation", False):
            return None, False

        hook_ctx = tool_context if tool_context is not None else {"history": conversation_history or []}
        hook_result = apply_pre_execute_hooks(tool, hook_ctx, {"query": user_query})
        if isinstance(hook_result, Reject) and hook_result.error_code == "confirmation_required":
            dry_run_result = execute_guarded(
                tool,
                user_query,
                context={
                    "history": conversation_history or [],
                    "dry_run": True,
                    "user": getattr(tool_context, "user", None),
                },
            )
            draft = dry_run_result.get("draft") if isinstance(dry_run_result, dict) else None
            if not draft:
                done = {"type": "done", "error": True}
                annotate_error_kind(
                    done,
                    dry_run_result.get("message", "工具未返回确认草案"),
                    tool_used=tool.name,
                    tool_result=dry_run_result,
                )
                return [sse_event(done)], True
            token = str(uuid.uuid4())
            set_confirmation_draft(
                token,
                {
                    "tool_name": tool.name,
                    "user_query": user_query,
                    "context_sig": scope_sig,
                    "task_id": getattr(tool_context, "task_id", None),
                    "draft": draft,
                },
            )
            public_draft = public_confirmation_draft(draft, tool.name)
            events = [
                sse_event({"type": "meta", "intent": intent, "tool_used": tool.name, "tool_result": {"draft": public_draft}}),
                sse_event(
                    {
                        "type": "confirmation",
                        "awaiting_confirmation": True,
                        "confirmation_token": token,
                        "draft": public_draft,
                        "answer": public_draft["summary"],
                    }
                ),
                sse_event({"type": "done", "error": False, "awaiting_confirmation": True}),
            ]
            return events, True
        # P1A-2 enforcement:非 confirmation_required 的 Reject(如 rate_limit_exceeded)
        # 直接阻断工具执行;yield done 事件(带 error_code/retry_after)后立即 return,
        # 不走 LLM 合成,不 yield 后续 chunk/meta 事件,避免 SSE 流被前端误判网络异常。
        if isinstance(hook_result, Reject) and hook_result.error_code != "confirmation_required":
            done_event = {
                "type": "done",
                "error": True,
                "error_code": hook_result.error_code,
                "retry_after": getattr(hook_result, "retry_after", None),
            }
            return [sse_event(done_event)], True
        # 既有路径(apply_pre_execute_hooks 内部已做失败降级,透传 params)
        return None, False

    def _execute_tool_with_cache(self, tool, user_query, conversation_history, tool_context, scope_sig):
        """原工具执行段:结果缓存优先,否则执行 + hook 链 + 缓存回写。

        返回 ``(tool_result, tool_name, sources, tool_fallback)``。
        """
        cached_result = get_cached_tool_result(tool.name, user_query, context_sig=scope_sig)
        if cached_result is not None:
            tool_result = cached_result
        else:
            hook_ctx = tool_context if tool_context is not None else {"history": conversation_history or []}
            try:
                # 与 process() 对称:超时熔断包装(修复 1)
                if tool_context is not None and getattr(tool, "supports_scope_filter", False):
                    base_qs = tool.build_base_queryset()
                    scoped_qs = tool.get_queryset_for_scope(base_qs, tool_context)
                    tool_result = execute_guarded(
                        tool,
                        params={"query": user_query},
                        scope=tool_context.scope,
                        qs=scoped_qs,
                    )
                else:
                    tool_result = execute_guarded(
                        tool,
                        user_query,
                        context={"history": conversation_history or []},
                    )
            except Exception as e:
                recovery = apply_failure_hooks(tool, e, hook_ctx)
                if recovery.action == "fallback" and isinstance(recovery.fallback_value, dict):
                    tool_result = recovery.fallback_value
                else:
                    tool_result = {"found": False, "message": f"工具执行失败: {str(e)}"}
            # POST_EXECUTE 钩子链:统一出口 PII 脱敏(缓存前)
            tool_result = apply_post_execute_hooks(tool, tool_result, hook_ctx)
            cache_tool_result(tool.name, user_query, tool_result, context_sig=scope_sig)

        tool_name, sources, tool_fallback = self._classify_tool_result(tool, tool_result)
        return tool_result, tool_name, sources, tool_fallback

    def _classify_tool_result(self, tool, tool_result):
        """原 found 判定:返回 (tool_name, sources, tool_fallback)。"""
        if isinstance(tool_result, dict) and not tool_result.get("found"):
            return tool.name, None, True
        sources = tool_result.get("sources") if isinstance(tool_result, dict) else None
        return tool.name, sources, False

    def _emit_single_answer(
        self, user_query, intent, tool_name, tool_result, tool_fallback, tool, conversation_history
    ):
        """原 Step 3:构造流式生成源并逐 chunk 发送,返回完整答案。"""
        if tool_fallback:
            # 工具已执行但未找到结果,带工具上下文告知 LLM
            answer, _ = generate_tool_empty_answer(user_query, tool_name, tool_result, conversation_history)

            def _gen():
                yield answer

            stream = _gen()
        elif tool:
            stream = generate_answer_stream(user_query, intent, tool_name, tool_result, conversation_history)
        else:
            answer, _ = generate_general_answer(user_query, conversation_history)

            def _gen2():
                yield answer

            stream = _gen2()

        # 累积流式内容,用于在结束信号中判定是否为失败响应
        stream_parts = []
        for chunk in stream:
            stream_parts.append(chunk)
            yield sse_event({"type": "chunk", "content": chunk})
        return "".join(stream_parts)
