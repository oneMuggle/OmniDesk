"""多工具链式处理模块(R3-A1 Task 5 拆分)。

自 ``orchestrator._process_chain`` 逐字提取,去 ``self`` 后改为模块级纯函数
``process_chain``;orchestrator 保留同名薄委托方法,外部行为零变化。

调用方:``AgentOrchestrator._process_chain``(薄委托)。
"""

from .result_synthesizer import ResultSynthesizer
from .tool_chain_executor import (
    execute_tool_chain,
    synthesize_answer as synthesize_chain_answer,
    ToolChainExecutor,
)
from .conversation_context import is_failed_answer


def process_chain(
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
