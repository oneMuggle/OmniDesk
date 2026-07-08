from .intent_classifier import (
    classify_intent,
    generate_answer,
    generate_answer_stream,
    generate_general_answer,
    generate_tool_empty_answer,
)
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
                try:
                    if tool_context is not None:
                        # 优先走 scope-aware 路径(若工具实现了 scope 抽象)
                        if getattr(tool, "supports_scope_filter", False):
                            base_qs = tool.build_base_queryset()
                            scoped_qs = tool.get_queryset_for_scope(base_qs, tool_context)
                            tool_result = tool.execute(
                                params={"query": user_query},
                                scope=tool_context.scope,
                                qs=scoped_qs,
                            )
                        else:
                            tool_result = tool.execute(
                                user_query,
                                context={"history": conversation_history or []},
                            )
                    else:
                        tool_result = tool.execute(
                            user_query,
                            context={"history": conversation_history or []},
                        )
                except Exception as e:
                    tool_result = {"found": False, "message": f"工具执行失败: {str(e)}"}
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
                }

            # Step 4: LLM 生成自然语言回答(先查缓存)
            if not has_history:
                cached_answer = get_cached_answer(user_query, intent, context_sig=scope_sig)
                if cached_answer:
                    answer = cached_answer
                    usage = None
                else:
                    answer, usage = generate_answer(user_query, intent, tool.name, tool_result, conversation_history)
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
            raw_results = execute_tool_chain(
                plan, user_query, context={"history": conversation_history or []}
            )
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
        }

    def process_stream(self, user_query: str, conversation_history: list = None, tool_context=None):
        """流式处理:先发送元数据,再逐 chunk 发送 LLM 输出"""
        import json

        has_history = conversation_history is not None and len(conversation_history) > 0
        scope_sig = _scope_cache_sig(tool_context)

        # Step 1: 意图分类
        schemas = ToolRegistry.get_all_schemas()
        intent = classify_intent(user_query, schemas, conversation_history)
        if not has_history:
            cache_intent(user_query, schemas, intent, context_sig=scope_sig)

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
                try:
                    if tool_context is not None and getattr(tool, "supports_scope_filter", False):
                        base_qs = tool.build_base_queryset()
                        scoped_qs = tool.get_queryset_for_scope(base_qs, tool_context)
                        tool_result = tool.execute(
                            params={"query": user_query},
                            scope=tool_context.scope,
                            qs=scoped_qs,
                        )
                    else:
                        tool_result = tool.execute(
                            user_query,
                            context={"history": conversation_history or []},
                        )
                except Exception as e:
                    tool_result = {"found": False, "message": f"工具执行失败: {str(e)}"}
                cache_tool_result(tool.name, user_query, tool_result, context_sig=scope_sig)

            # 工具失败时 fallback 到通用回答
            if isinstance(tool_result, dict) and not tool_result.get("found"):
                tool_name = tool.name
                tool_fallback = True
            else:
                tool_name = tool.name
                sources = tool_result.get("sources") if isinstance(tool_result, dict) else None

        # 先发送元数据
        meta = json.dumps(
            {
                "type": "meta",
                "intent": intent,
                "tool_used": tool_name,
                "tool_result": tool_result,
                "sources": sources,
                "tool_fallback": tool_fallback,
            },
            ensure_ascii=False,
        )
        yield f"data: {meta}\n\n"

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

        for chunk in stream:
            data = json.dumps({"type": "chunk", "content": chunk}, ensure_ascii=False)
            yield f"data: {data}\n\n"

        # 发送结束信号
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
