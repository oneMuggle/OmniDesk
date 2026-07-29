import json

from .intent_classifier import (
    classify_intent,
    generate_answer,
    generate_answer_stream,
    generate_general_answer,
    generate_tool_empty_answer,
)
from .conversation_context import is_failed_answer
from ..models import LlmAppConfig
from ..tools.registry import ToolRegistry
from ..cache import (
    get_cached_intent,
    cache_intent,
    get_cached_tool_result,
    cache_tool_result,
    get_cached_answer,
    cache_answer,
)
from .tool_chain_planner import generate_tool_chain_plan
from .tool_chain_executor import (
    execute_tool_chain,
    synthesize_answer as synthesize_chain_answer,
    ToolChainExecutor,
)
from .result_synthesizer import ResultSynthesizer
from ..hooks.wiring import (
    apply_failure_hooks,
    apply_post_execute_hooks,
    execute_guarded,
)


# ---------------------------------------------------------------------------
# 后端输出契约（与前端共享，机器可读；借鉴 claw-code 的 doctor 契约思路）
# ---------------------------------------------------------------------------

# SSE 事件契约版本号：所有 meta/chunk/done/session 事件均携带
FORMAT_VERSION = 1

# 错误分类 → 可操作的中文指引（前端按 kind 决定提示样式与跳转入口）
ERROR_KIND_HINTS = {
    "no_llm_endpoint": "请前往管理后台 → AI 应用配置 LLM 端点",
    "llm_unavailable": "LLM 服务暂时不可用，请稍后重试或检查端点连通性",
    "ragflow_unavailable": "知识库服务暂时不可用",
    "internal_error": "服务异常，请稍后重试",
}


def _has_active_llm_config() -> bool:
    """是否存在激活的智能助手 LLM 应用配置（且其端点同样激活）。"""
    return LlmAppConfig.objects.filter(
        app_name="smart_assistant",
        is_active=True,
        endpoint__is_active=True,
    ).exists()


def _mentions_ragflow(answer, tool_result) -> bool:
    """判断错误信息是否涉及 Ragflow（大小写不敏感）。"""
    haystacks = [str(answer or "")]
    if isinstance(tool_result, dict):
        for key in ("message", "error", "detail"):
            value = tool_result.get(key)
            if isinstance(value, str):
                haystacks.append(value)
    elif isinstance(tool_result, str):
        haystacks.append(tool_result)
    return any("ragflow" in text.lower() for text in haystacks)


def classify_error_kind(result: dict):
    """判定编排结果的机器可读错误分类（kind）。

    输出契约判定规则（优先级自上而下）：
    - 非失败响应（error 为假且回答无失败前缀）→ 返回 ``None``
    - knowledge_qa 工具失败且错误涉及 Ragflow → ``"ragflow_unavailable"``
    - 无激活的 LLM 应用配置/端点 → ``"no_llm_endpoint"``
    - 有配置但 LLM 回答生成失败 → ``"llm_unavailable"``
    - 其他失败（如显式 error 标记但回答无失败前缀）→ ``"internal_error"``

    保持纯函数 + 单次 DB 查询的形式，便于单测（需 django_db）。
    """
    if not (bool(result.get("error")) or is_failed_answer(result.get("answer"))):
        return None
    tool_used = result.get("tool_used") or ""
    if tool_used == "knowledge_qa" and _mentions_ragflow(result.get("answer"), result.get("tool_result")):
        return "ragflow_unavailable"
    if not _has_active_llm_config():
        return "no_llm_endpoint"
    if is_failed_answer(result.get("answer")):
        return "llm_unavailable"
    return "internal_error"


def sse_event(payload: dict) -> str:
    """序列化单条 SSE 事件：统一附带契约版本号 ``format_version``。"""
    return f"data: {json.dumps({'format_version': FORMAT_VERSION, **payload}, ensure_ascii=False)}\n\n"


def annotate_error_kind(payload: dict, answer: str, tool_used=None, tool_result=None) -> dict:
    """为失败事件载荷追加 ``kind`` + ``hint``（输出契约）。

    供 orchestrator 的 done 事件与视图层的 session/同步响应复用，
    保证同一失败场景在各出口拿到一致的错误分类。
    """
    kind = classify_error_kind(
        {
            "answer": answer,
            "error": True,
            "tool_used": tool_used,
            "tool_result": tool_result,
        }
    )
    payload["kind"] = kind
    payload["hint"] = ERROR_KIND_HINTS.get(kind, ERROR_KIND_HINTS["internal_error"])
    return payload


def _scope_cache_sig(tool_context):
    """从 ToolContext 派生 cache 隔离签名,防止跨用户缓存投毒。

    返回形如 ``u<user_pk>_s<scope_value>`` 的短串,拼到 cache key 里。
    tool_context 为 None 时退化为 ``anonymous``,与原行为兼容(空 sig)。
    """
    if tool_context is None or tool_context.user is None:
        return "anonymous"
    user = tool_context.user
    user_pk = getattr(user, "pk", None) or getattr(user, "id", None) or "anon"
    scope = getattr(tool_context, "scope", None)
    scope_value = scope.value if hasattr(scope, "value") else str(scope or "self")
    return f"u{user_pk}_s{scope_value}"


class AgentOrchestrator:
    """Agent 编排器：意图分类 → 工具选择 → 回答生成

    支持单工具执行和多工具链式执行。

    Task 17 增强:
    - ``process()`` / ``process_stream()`` 接受 ``tool_context``(``ToolContext`` 实例);
      用于 scope-aware 跨模块汇总路径,以及 cache key 隔离。
    - 多工具路径走 ``ToolChainExecutor``(class 版,支持 scope 注入),并通过
      ``ResultSynthesizer`` 把多工具结果聚合成前端 ``<AggregatedDayCard>`` 直接消费的结构。
    - 返回 ``intent="aggregated_day"``,让前端 ``ToolResult.jsx`` 触发 ``AggregatedDayCard`` 渲染。
    """

    def process(self, user_query: str, conversation_history: list = None, tool_context=None) -> dict:
        """处理用户问题"""
        schemas = ToolRegistry.get_all_schemas()
        has_history = conversation_history is not None and len(conversation_history) > 0

        # Step 1: 意图分类(先查缓存)
        # 缓存 key 中纳入 scope(由 tool_context 派生),避免不同权限用户读到
        # 彼此的 intent 分类结果。
        scope_sig = _scope_cache_sig(tool_context)

        if not has_history:
            cached_intent = get_cached_intent(user_query, schemas, context_sig=scope_sig)
            if cached_intent:
                intent = cached_intent
            else:
                intent = classify_intent(user_query, schemas, conversation_history)
                cache_intent(user_query, schemas, intent, context_sig=scope_sig)
        else:
            intent = classify_intent(user_query, schemas, conversation_history)

        # Step 2: 检测是否需要多工具
        tool_chain = generate_tool_chain_plan(user_query, schemas, conversation_history)

        if tool_chain:
            # 多工具链式执行 — Task 17: 走 scope-aware 路径
            return self._process_chain(user_query, tool_chain, conversation_history, tool_context)

        # Step 3: 单工具路由(保持现有路径)
        tool = ToolRegistry.get_tool(intent)
        if tool:
            cached_result = get_cached_tool_result(tool.name, user_query, context_sig=scope_sig)
            if cached_result is not None:
                tool_result = cached_result
            else:
                hook_ctx = tool_context if tool_context is not None else {"history": conversation_history or []}
                try:
                    # 工具执行统一经 execute_guarded 超时熔断包装(修复 1)
                    if tool_context is not None and getattr(tool, "supports_scope_filter", False):
                        # scope-aware 路径(工具实现了 scope 抽象)
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
                    # ON_FAILURE 钩子链先介入:给出结构化 fallback 时采用,
                    # 否则保留原错误结构
                    recovery = apply_failure_hooks(tool, e, hook_ctx)
                    if recovery.action == "fallback" and isinstance(recovery.fallback_value, dict):
                        tool_result = recovery.fallback_value
                    else:
                        tool_result = {"found": False, "message": f"工具执行失败: {str(e)}"}
                # POST_EXECUTE 钩子链:统一出口 PII 脱敏。必须在缓存之前,
                # 否则缓存命中路径会绕过脱敏
                tool_result = apply_post_execute_hooks(tool, tool_result, hook_ctx)
                cache_tool_result(tool.name, user_query, tool_result, context_sig=scope_sig)

            # 工具执行成功但未找到结果时,带工具上下文告知 LLM
            if isinstance(tool_result, dict) and not tool_result.get("found"):
                answer, usage = generate_tool_empty_answer(user_query, tool.name, tool_result, conversation_history)
                return {
                    "answer": answer,
                    "intent": intent,
                    "tool_used": tool.name,
                    "tool_result": tool_result,
                    "sources": None,
                    "tool_fallback": True,
                    "usage": usage,
                    "error": is_failed_answer(answer),
                }

            # Step 4: LLM 生成自然语言回答(先查缓存)
            if not has_history:
                cached_answer = get_cached_answer(user_query, intent, context_sig=scope_sig)
                if cached_answer:
                    answer = cached_answer
                    usage = None
                else:
                    answer, usage = generate_answer(user_query, intent, tool.name, tool_result, conversation_history)
                    # 失败响应不进缓存,避免错误文本被后续请求反复命中
                    if not is_failed_answer(answer):
                        cache_answer(user_query, intent, answer, context_sig=scope_sig)
            else:
                answer, usage = generate_answer(user_query, intent, tool.name, tool_result, conversation_history)

            return {
                "answer": answer,
                "intent": intent,
                "tool_used": tool.name,
                "tool_result": tool_result,
                "sources": tool_result.get("sources") if isinstance(tool_result, dict) else None,
                "usage": usage,
                "error": is_failed_answer(answer),
            }
        else:
            # 通用对话
            answer, usage = generate_general_answer(user_query, conversation_history)
            return {
                "answer": answer,
                "intent": "general_chat",
                "tool_used": None,
                "tool_result": None,
                "sources": None,
                "usage": usage,
                "error": is_failed_answer(answer),
            }

    def _process_chain(
        self,
        user_query: str,
        plan: list,
        conversation_history: list,
        tool_context=None,
    ) -> dict:
        """多工具链式处理。

        Task 17 行为变更:
        - 优先走 ``ToolChainExecutor``(class 版)以注入 scope/user;
          若未提供 tool_context 则降级到旧函数版 ``execute_tool_chain`` 保持兼容。
        - 用 ``ResultSynthesizer`` 把多工具结果聚合成前端可消费的 dict。
        - 返回 ``intent="aggregated_day"``,触发前端 ``<AggregatedDayCard>`` 渲染。
        """
        if tool_context is not None:
            executor_results = ToolChainExecutor().execute({"steps": plan}, tool_context)
        else:
            raw_results = execute_tool_chain(plan, user_query, context={"history": conversation_history or []})
            executor_results = [r.get("result", {}) for r in raw_results if r.get("result")]

        # 聚合多工具结果(供前端 <AggregatedDayCard> 渲染)
        synthesized = ResultSynthesizer().synthesize(executor_results, user_query)

        # LLM 合成自然语言回答
        first_tool = plan[0].get("tool") if plan else None
        try:
            answer = synthesize_chain_answer(plan, executor_results, user_query)
        except Exception:
            answer = synthesized["summary"]

        # 收集所有 source
        all_sources = []
        for r in executor_results:
            if isinstance(r, dict):
                sources = r.get("sources")
                if sources:
                    all_sources.extend(sources)

        return {
            "answer": answer,
            "intent": "aggregated_day",  # Task 17: 关键改名,触发 AggregatedDayCard
            "tool_used": first_tool,
            "tool_result": {
                # ResultSynthesizer 输出(camelCase)直接供前端 AggregatedDayCard 消费
                "summary": synthesized["summary"],
                "items": synthesized["items"],
                "total_count": synthesized["total_count"],
                "moduleCounts": synthesized["moduleCounts"],
                # 兼容字段:保留 chain_results 供调试/旧前端代码读取
                "chain_results": executor_results,
            },
            "sources": all_sources if all_sources else None,
            "tool_chain": plan,
            "error": is_failed_answer(answer),
        }

    def process_stream(self, user_query: str, conversation_history: list = None, tool_context=None):
        """流式处理:先发送元数据,再逐 chunk 发送 LLM 输出。

        Task 17 修复:在执行单工具路径前,先调用 ``generate_tool_chain_plan()``
        检测多工具场景;若命中,走 ``_process_chain()`` 让流式前端也能拿到
        ``aggregated_day`` 结构,触发 ``<AggregatedDayCard>`` 渲染。

        Task 2 增强(SAIS Plan 1):在入口先查回答缓存,命中时直接 yield
        cached answer + done,跳过完整编排(LLM 调用 + 工具执行)。

        输出契约:所有事件(meta/chunk/done)统一携带 ``format_version``;
        失败时 done 事件追加机器可读的 ``kind`` + 中文 ``hint``。
        """
        has_history = conversation_history is not None and len(conversation_history) > 0
        scope_sig = _scope_cache_sig(tool_context)

        # Step 1: 意图分类
        schemas = ToolRegistry.get_all_schemas()

        # Task 2 of feat/sa-e2e-scenarios: 流式路径回答缓存短路
        # 若缓存命中且无对话历史,直接 yield cached answer + done,跳过 LLM 调用。
        intent = None
        if not has_history:
            cached_intent = get_cached_intent(user_query, schemas, context_sig=scope_sig)
            if cached_intent:
                intent = cached_intent
            else:
                intent = classify_intent(user_query, schemas, conversation_history)
                cache_intent(user_query, schemas, intent, context_sig=scope_sig)

            cached_answer = get_cached_answer(user_query, intent, context_sig=scope_sig)
            if cached_answer:
                # 缓存命中,直接 yield 完整 answer + done(不动 LLM)
                yield sse_event({"type": "meta", "intent": intent, "cache_hit": True})
                yield sse_event({"type": "chunk", "content": cached_answer})
                done = {"type": "done", "cache_hit": True, "error": is_failed_answer(cached_answer)}
                if done["error"]:
                    annotate_error_kind(done, cached_answer)
                yield sse_event(done)
                return

        # Step 1.5 (Task 17): 检测多工具链式执行
        # 与 process() 对称:命中多工具计划时,先走 _process_chain() 拿到
        # 聚合结果(intent="aggregated_day"),再以流式事件流的形式
        # 推给前端(避免流式场景下永远拿不到 moduleCounts)。
        tool_chain = generate_tool_chain_plan(user_query, schemas, conversation_history)
        if tool_chain:
            chain_result = self._process_chain(user_query, tool_chain, conversation_history, tool_context)
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
            return

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

            # 工具失败时 fallback 到通用回答
            if isinstance(tool_result, dict) and not tool_result.get("found"):
                tool_name = tool.name
                tool_fallback = True
            else:
                tool_name = tool.name
                sources = tool_result.get("sources") if isinstance(tool_result, dict) else None

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

        # Step 3: 流式生成回答
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

        # 发送结束信号(携带错误标记,供 view 层决定是否落库)
        full_answer = "".join(stream_parts)
        done = {"type": "done", "error": is_failed_answer(full_answer)}
        if done["error"]:
            annotate_error_kind(done, full_answer, tool_used=tool_name, tool_result=tool_result)
        yield sse_event(done)
