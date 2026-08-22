"""Agent 编排器公开入口(R5-D5 拆分:orchestrator/entry.py)。

AgentOrchestrator 主类:公开 process / process_stream 入口与原生 tool_calls
路径方法。legacy JSON 路径方法集在 persistence.LegacyProcessMixin,路径决策
逻辑在 run_path.RunPathResolver。行为零变化。
"""

from observability import get_logger

from ..native_tool_runner import execute_native_tool
from .run_path import RunPathResolver
from .persistence import LegacyProcessMixin
from .result_wrap import ResultWrapMixin


logger = get_logger(__name__, "smart_assistant")


class AgentOrchestrator(ResultWrapMixin, LegacyProcessMixin):
    """Agent 编排器：意图分类 → 工具选择 → 回答生成

    支持单工具执行和多工具链式执行。

    Task 17 增强:
    - ``process()`` / ``process_stream()`` 接受 ``tool_context``(``ToolContext`` 实例);
      用于 scope-aware 跨模块汇总路径,以及 cache key 隔离。
    - 多工具路径走 ``ToolChainExecutor``(class 版,支持 scope 注入),并通过
      ``ResultSynthesizer`` 把多工具结果聚合成前端 ``<AggregatedDayCard>`` 直接消费的结构。
    - 返回 ``intent="aggregated_day"``,让前端 ``ToolResult.jsx`` 触发 ``AggregatedDayCard`` 渲染。

    Task 6 增强(SAIS Plan 1):
    - 持有 ``self.router = LLMRouter(app_name="smart_assistant")``,原生
      tool_calls 路径直接调 ``router.generate_with_tools()``;
    - JSON 路径仍走 ``router.generate()``(向后兼容)。

    R5-D5 拆分:legacy JSON 路径(_legacy_* 家族)移至
    ``persistence.LegacyProcessMixin``;use_native 决策与 endpoint 能力检查
    移至 ``run_path.RunPathResolver``;本文件保留公开入口与原生路径。
    """

    # 路径决策(原 process() 内联判定段与 _endpoint_supports_tool_calls 的搬运委托)
    _resolve_native = staticmethod(RunPathResolver.resolve_native_decision)
    _endpoint_supports_tool_calls = staticmethod(RunPathResolver.endpoint_supports_tool_calls)

    def __init__(self) -> None:
        """初始化 LLM router(按 app_name 隔离,默认 smart_assistant)。"""
        # 延迟导入避免模块加载期循环
        from llm_service.router import LLMRouter

        self.router = LLMRouter(app_name="smart_assistant")

    def process(
        self,
        user_query: str | None = None,
        conversation_history: list | None = None,
        tool_context=None,
        *,
        query: str | None = None,
        llm_messages: list | None = None,
        use_native_tool_calls: bool | None = None,
    ) -> dict:
        """处理用户问题。

        Task 6 增强(SAIS Plan 1):
        - 新增可选 kwarg ``use_native_tool_calls``(默认 ``None`` = 自动判断):
          - ``None``:依 ``settings.USE_NATIVE_TOOL_CALLS + _endpoint_supports_tool_calls()``
            决定走 ``_process_tool_calls_path``(原生 tool_calls)或
            ``_process_json_path``(JSON 解析旧路径)。
          - ``True``/``False``:强制指定。
        - 同时支持 ``query`` kwarg(新代码约定)与位置参数 ``user_query``(旧代码约定)。
        - 默认行为 100% 对等于旧实现(返回 dict,所有现有调用方不受影响)。
        - 新路径异常时自动降级到 JSON 路径,不抛异常给视图层。

        Task 12 灰度(L1):
        - ``use_native_tool_calls=None`` 自动判断时叠加 staff 门控:
          默认仅 ``context.user.is_staff=True`` 用户走原生路径;
          ``settings.USE_NATIVE_TOOL_CALLS_FOR_ALL=True`` 时全员开放。
        - 无用户上下文(内部调用)按非 staff 处理,走 JSON 路径。
        """
        # 兼容 query=user_query(new code) 与 user_query(legacy)
        if query is None:
            query = user_query
        if query is None:
            raise TypeError("process() 需要 query 或 user_query 参数")

        # 决定走哪条路径(原内联判定段搬运至 RunPathResolver,行为逐字等价)
        use_native = self._resolve_native(
            use_native_tool_calls=use_native_tool_calls,
            tool_context=tool_context,
            endpoint_supports_tool_calls_fn=self._endpoint_supports_tool_calls,
        )

        if use_native:
            # 新路径:返回 tuple(content, usage, meta)
            try:
                from smart_assistant.tools.tool_context import ToolContext

                if tool_context is None:
                    tool_context = ToolContext(user=None)
                if llm_messages is None:
                    llm_messages = self._build_initial_messages(query, tool_context, conversation_history)
                content, usage, meta = self._process_tool_calls_path(
                    query=query, context=tool_context, llm_messages=llm_messages
                )
                return self._wrap_native_to_dict(content, usage, meta)
            except Exception as exc:
                # 降级策略:新路径异常 → JSON 路径兜底
                logger.warning("tool_calls 路径异常,降级到 JSON 路径: %s", exc, exc_info=True)
                # 回退:用 JSON 路径再跑一遍
                try:
                    content, usage, meta = self._process_json_path(
                        query=query,
                        context=tool_context,
                        llm_messages=llm_messages,
                    )
                    return self._wrap_native_to_dict(content, usage, meta)
                except Exception:
                    # JSON 路径也失败 → 走最原始的 legacy 路径(digest/chat.py 已能处理异常)
                    return self._legacy_process(query, conversation_history, tool_context)

        # 走 JSON 路径:调用 _process_json_path(测试期望入口),并把
        # tuple 转回 dict 保持向后兼容。
        content, usage, meta = self._process_json_path(
            query=query,
            context=tool_context,
            llm_messages=llm_messages,
            conversation_history=conversation_history,
        )
        return self._wrap_native_to_dict(content, usage, meta)

    def _build_initial_messages(
        self,
        user_query: str,
        context,
        conversation_history: list | None,
    ) -> list:
        """构造 LLM 初始 messages 列表(原生 tool_calls 路径使用)。

        返回 OpenAI 兼容格式::
            [
                {"role": "system", "content": "你是 OmniDesk 助手..."},
                {"role": "user", "content": user_query},
            ]

        历史消息以原样追加到 system 之后;若 ``llm_messages`` 已在外部
        构造完成,直接透传(避免重复包 system prompt)。
        """
        messages = []
        messages.append(
            {
                "role": "system",
                "content": "你是 OmniDesk 智能助手,负责按用户请求调用合适的工具完成任务。",
            }
        )
        if conversation_history:
            for m in conversation_history:
                if isinstance(m, dict) and m.get("role") in ("user", "assistant", "tool", "system"):
                    messages.append(m)
        messages.append({"role": "user", "content": user_query})
        return messages

    # === 原生 tool_calls 路径的单个工具执行(提取至 native_tool_runner,保留薄委托) ===

    def _execute_native_tool(self, tool, validated, context):
        """兼容委托:指向模块级 execute_native_tool(行为不变)。"""
        return execute_native_tool(tool, validated, context)

    def _process_tool_calls_path(
        self,
        *,
        query: str,
        context,
        llm_messages: list,
    ) -> tuple[str, dict, dict]:
        """原生 tool_calls 主循环(非流式,spec §3.4)。

        委托 ``_run_tool_calls_rounds`` 完成工具轮,取其 ``content`` 返回。
        流式路径(``_process_stream_tool_calls_path``)复用同一工具轮,再做
        流式最终轮。对外行为与 L1 完全一致。
        """
        content, usage, meta, _tool_round_messages = self._run_tool_calls_rounds(
            query=query, context=context, llm_messages=llm_messages
        )
        return content, usage, meta

    def _run_tool_calls_rounds(
        self,
        *,
        query: str,
        context,
        llm_messages: list,
    ) -> tuple[str, dict, dict, list]:
        """原生 tool_calls 工具轮(已提取至 tool_rounds_runner,保留薄委托)。

        行为与提取前一致:
        - 最多 ``settings.MAX_TOOL_CALLS_ROUNDS`` 轮(默认 3);
        - confirm-replay 工具提前返回 awaiting_confirmation。

        返回 ``(content, usage, meta, tool_round_messages)``(语义见
        ``tool_rounds_runner.run_tool_calls_rounds`` docstring)。
        """
        from ..tool_rounds_runner import run_tool_calls_rounds

        return run_tool_calls_rounds(
            self.router,
            query=query,
            context=context,
            llm_messages=llm_messages,
            json_fallback=self._process_json_path,
        )

    def _process_chain(
        self,
        user_query: str,
        plan: list,
        conversation_history: list,
        tool_context=None,
    ) -> dict:
        """多工具链式处理(Task 5 拆分:薄委托 tool_chain_runner.process_chain)。

        多工具结果经 ``ToolChainExecutor`` / ``ResultSynthesizer`` 聚合,
        返回 ``intent="aggregated_day"`` 触发前端 ``<AggregatedDayCard>`` 渲染。
        实现见 ``tool_chain_runner.process_chain``。
        """
        from ..tool_chain_runner import process_chain

        return process_chain(user_query, plan, conversation_history, tool_context)

    def process_stream(
        self,
        user_query: str,
        conversation_history: list = None,
        tool_context=None,
        use_native_tool_calls: bool | None = None,
    ):
        """流式处理入口(委托 StreamRunner,行为不变)。"""
        from ..stream_runner import StreamRunner

        yield from StreamRunner(self).stream(
            user_query,
            conversation_history=conversation_history,
            tool_context=tool_context,
            use_native_tool_calls=use_native_tool_calls,
        )
