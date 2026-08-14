import uuid

from django.conf import settings

from observability import get_logger

from .intent_classifier import (
    classify_intent,
    generate_answer,
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
    set_confirmation_draft,
)
from .tool_chain_planner import generate_tool_chain_plan
from .sse_contract import (
    ERROR_KIND_HINTS as ERROR_KIND_HINTS,
    FORMAT_VERSION as FORMAT_VERSION,
    annotate_error_kind as annotate_error_kind,
    classify_error_kind as classify_error_kind,
    sse_event as sse_event,
)
from .orchestrator_helpers import _dict_to_query as _dict_to_query, _scope_cache_sig
from .native_tool_runner import execute_native_tool
from ..hooks.base import Reject
from ..hooks.wiring import (
    apply_failure_hooks,
    apply_post_execute_hooks,
    apply_pre_execute_hooks,
    execute_guarded,
)


logger = get_logger(__name__, "smart_assistant")


class AgentOrchestrator:
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
    """

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

        # 决定走哪条路径
        if use_native_tool_calls is None:
            try:
                # L1 灰度(Task 12):默认仅 is_staff=True 用户启用原生 tool_calls
                # 路径;settings.USE_NATIVE_TOOL_CALLS_FOR_ALL=True 时全员开放。
                # 无用户上下文(内部调用)按非 staff 处理,降级到 JSON 路径更保守。
                user_is_staff = bool(
                    tool_context is not None
                    and getattr(tool_context, "user", None) is not None
                    and bool(getattr(tool_context.user, "is_staff", False))
                )
                use_native = (
                    bool(getattr(settings, "USE_NATIVE_TOOL_CALLS", False))
                    and self._endpoint_supports_tool_calls()
                    and (user_is_staff or bool(getattr(settings, "USE_NATIVE_TOOL_CALLS_FOR_ALL", False)))
                )
            except Exception:
                logger.warning("_endpoint_supports_tool_calls 检查失败,降级到 JSON 路径", exc_info=True)
                use_native = False
        else:
            use_native = bool(use_native_tool_calls)

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

    def _legacy_process(
        self,
        user_query: str,
        conversation_history: list | None,
        tool_context,
    ) -> dict:
        """旧 process() 实现的逐字提取(Task 6 拆分)。

        行为完全对等于 Task 6 之前的 process();A/B 评估期间
        ``_process_json_path()`` 调用时同样跑这套逻辑。
        """
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
            hook_ctx = tool_context if tool_context is not None else {"history": conversation_history or []}

            # === confirm-replay 框架:require_confirmation 工具拦截 ===
            # Phase B:orchestrator 在 execute 前调 pre-hook 链。若工具标记
            # require_confirmation=True 且 pre-hook 返回 Reject(error_code=
            # "confirmation_required"),则工具"预演"(dry_run)返回 draft,
            # orchestrator 把 draft 存到短期缓存,返回 awaiting_confirmation
            # 给前端,等用户二次确认。
            if getattr(tool, "require_confirmation", False):
                hook_result = apply_pre_execute_hooks(tool, hook_ctx, {"query": user_query})
                if isinstance(hook_result, Reject) and hook_result.error_code == "confirmation_required":
                    # 工具预演:dry_run=True 让工具内部跳过副作用,只返回 draft
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
                        # 工具未支持 dry_run 模式,返回错误
                        return {
                            "answer": f"工具 {tool.name} 标记为需要确认,但未返回预演结果(draft),请联系管理员",
                            "intent": intent,
                            "tool_used": tool.name,
                            "tool_result": None,
                            "awaiting_confirmation": False,
                            "error": True,
                        }
                    # 存 draft 到短期缓存(TTL 10 分钟)
                    token = str(uuid.uuid4())
                    set_confirmation_draft(
                        token,
                        {
                            "tool_name": tool.name,
                            "user_query": user_query,
                            "context_sig": scope_sig,
                            "draft": draft,
                        },
                    )
                    # 不走 LLM 合成,直接返回 awaiting_confirmation 给前端
                    return {
                        "answer": draft.get("summary") or "请确认以下操作",
                        "intent": intent,
                        "tool_used": tool.name,
                        "tool_result": {"draft": draft},
                        "awaiting_confirmation": True,
                        "confirmation_token": token,
                        "error": False,
                    }
                # 非 confirmation_required 的 Reject(如 rate_limit_exceeded):
                # 直接阻断工具执行,不走 LLM 合成;返回 error_code + retry_after 给视图层透传(P1A-2 enforcement)。
                # 与既有 confirmation 路径对称(按 error_code 判断,不动 confirmation_required 透传)。
                if isinstance(hook_result, Reject) and hook_result.error_code != "confirmation_required":
                    return {
                        "answer": hook_result.reason,
                        "intent": intent,
                        "tool_used": tool.name,
                        "tool_result": None,
                        "error": True,
                        "error_code": hook_result.error_code,
                        "retry_after": getattr(hook_result, "retry_after", None),
                    }
                # 既有路径(apply_pre_execute_hooks 内部已做失败降级,透传 params)
            # === confirm-replay 拦截结束 ===

            cached_result = get_cached_tool_result(tool.name, user_query, context_sig=scope_sig)
            if cached_result is not None:
                tool_result = cached_result
            else:
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
                # Task 7 of feat/sa-office-files:_legacy_process 仅在 JSON
                # 路径下被调用,显式传入 tool_call_path="json" 以避免
                # 与未来 native 路径的同 query 缓存污染。
                cached_answer = get_cached_answer(user_query, intent, context_sig=scope_sig, tool_call_path="json")
                if cached_answer:
                    answer = cached_answer
                    usage = None
                else:
                    answer, usage = generate_answer(user_query, intent, tool.name, tool_result, conversation_history)
                    # 失败响应不进缓存,避免错误文本被后续请求反复命中
                    if not is_failed_answer(answer):
                        cache_answer(user_query, intent, answer, context_sig=scope_sig, tool_call_path="json")
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

    # === Task 6:原生 tool_calls 路径(L1 §3.4)===

    def _endpoint_supports_tool_calls(self) -> bool:
        """检查当前激活的 LlmEndpoint 是否声明支持 native_tool_calls。

        读 ``LlmEndpoint.model_capabilities``(JSONField,默认为 list)。
        契约:若 model_capabilities 是 ``list[dict]``,且任一元素包含
        ``native_tool_calls=True``,则返回 ``True``。

        安全降级:无激活 endpoint / capabilities 为空 / 数据异常 → 返回
        ``False``,orchestrator 自动降级到 JSON 路径,避免老端点被错配。
        """
        try:
            config = (
                LlmAppConfig.objects.select_related("endpoint")
                .filter(is_active=True, app_name="smart_assistant", endpoint__is_active=True)
                .order_by("endpoint__priority", "endpoint__is_fallback")
                .first()
            )
        except Exception:
            logger.warning("查询 LlmAppConfig 失败,降级 JSON 路径", exc_info=True)
            return False

        if config is None:
            return False

        caps = getattr(config.endpoint, "model_capabilities", None)
        if not isinstance(caps, list):
            return False
        for cap in caps:
            if isinstance(cap, dict) and cap.get("native_tool_calls") is True:
                return True
        return False

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
        from .tool_rounds_runner import run_tool_calls_rounds

        return run_tool_calls_rounds(
            self.router,
            query=query,
            context=context,
            llm_messages=llm_messages,
            json_fallback=self._process_json_path,
        )

    def _process_json_path(
        self,
        *,
        query: str,
        context,
        llm_messages: list | None,
        conversation_history: list | None = None,
    ) -> tuple[str, dict, dict]:
        """JSON 解析路径(spec §3.4)。

        业务行为 100% 对等于旧 ``process()`` —— 这是 fallback 路径,
        A/B 评估期间两条路径的回答质量必须对等。

        当前实现:委托 ``_legacy_process`` 执行旧逻辑,再把 dict 结果
        转换为 ``(content, usage, meta)`` 三元组。

        参数:
            query: 用户问题
            context: ToolContext(用于 scope 派生)
            llm_messages: LLM 初始 messages(可选);若未提供,从
                conversation_history 派生。
            conversation_history: 对话历史(优先于 llm_messages,旧版约定)
        """
        # 把 llm_messages 转换为旧版 conversation_history(若提供且未传 history)
        if conversation_history is None and llm_messages:
            conversation_history = []
            for msg in llm_messages:
                if isinstance(msg, dict) and msg.get("role") in ("user", "assistant", "tool"):
                    role = msg["role"]
                    if role == "tool":
                        continue  # tool 消息不进入历史(legacy 不识别)
                    conversation_history.append({"role": role, "content": msg.get("content", "")})

        result = self._legacy_process(query, conversation_history, context)

        # 从 dict 提取 content / usage,构造 meta
        content = result.get("answer", "")
        usage = result.get("usage") or {}
        meta = {
            "tool_calls_meta": [],
            "tool_calls_rounds": 0,
            "tool_call_path": "json",
            # 透传旧字段供下游审计使用
            "intent": result.get("intent"),
            "tool_used": result.get("tool_used"),
            "tool_result": result.get("tool_result"),
            "sources": result.get("sources"),
            "tool_fallback": result.get("tool_fallback", False),
            "tool_chain": result.get("tool_chain"),
            # P1A-2 enforcement:_legacy_process 在 RateLimitHook Reject 时返回的
            # error_code / retry_after 必须透传到 meta,下游 _wrap_native_to_dict
            # 复制给视图层,前端才能拿到 retry-after 退避秒数。
            "error_code": result.get("error_code"),
            "retry_after": result.get("retry_after"),
            "awaiting_confirmation": result.get("awaiting_confirmation", False),
            "confirmation_token": result.get("confirmation_token"),
            "error": result.get("error", False),
        }
        return content, usage, meta

    def _wrap_native_to_dict(
        self,
        content: str,
        usage: dict,
        meta: dict,
    ) -> dict:
        """把原生路径的三元组包装为旧版 dict 格式(向后兼容)。

        现有视图层(digest.py / views/chat.py)读 ``result["answer"]`` /
        ``result["tool_used"]`` 等字段;包装器保证这些键仍可用。
        """
        tool_path = meta.get("tool_call_path", "native")
        if tool_path == "native":
            # 原生路径尚未完整跑通 intent 分类/工具链规划,只能填部分字段;
            # tool_used 从 tool_calls_meta 首条记录派生(LLM 实际调用的工具)。
            tool_meta = meta.get("tool_calls_meta") or []
            tool_used = tool_meta[0].get("tool") if tool_meta and isinstance(tool_meta[0], dict) else None
            awaiting = meta.get("awaiting_confirmation", False)
            out = {
                "answer": content,
                "intent": None,
                "tool_used": tool_used,
                "tool_result": None,
                "sources": None,
                "usage": usage,
                "error": is_failed_answer(content),
                # confirm-replay 透传(与 _legacy_process 的 awaiting_confirmation
                # 契约一致):前端据此展示确认按钮,带 token 二次请求重放工具。
                "awaiting_confirmation": awaiting,
                "confirmation_token": meta.get("confirmation_token"),
                # 审计字段(供 AgentLog 落库)
                "tool_call_path": tool_path,
                "tool_calls_meta": meta.get("tool_calls_meta", []),
                "tool_calls_rounds": meta.get("tool_calls_rounds", 0),
            }
            if awaiting:
                # 与 legacy 路径一致:确认场景下 tool_result 携带 draft 供前端展示
                out["tool_result"] = {"draft": meta.get("draft")}
            return out
        # JSON 路径的 meta 已经携带了旧字段,直接展开
        out = {
            "answer": content,
            "usage": usage,
            "tool_call_path": tool_path,
            "tool_calls_meta": meta.get("tool_calls_meta", []),
            "tool_calls_rounds": meta.get("tool_calls_rounds", 0),
        }
        for k in (
            "intent",
            "tool_used",
            "tool_result",
            "sources",
            "tool_fallback",
            "tool_chain",
            "awaiting_confirmation",
            "confirmation_token",
            "error",
            # P1A-2 enforcement:RateLimitHook Reject 时 _process_json_path 把
            # error_code / retry_after 写入 meta,这里复制给视图层。
            "error_code",
            "retry_after",
        ):
            if k in meta:
                out[k] = meta[k]
        return out

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
        from .tool_chain_runner import process_chain

        return process_chain(user_query, plan, conversation_history, tool_context)

    def process_stream(
        self,
        user_query: str,
        conversation_history: list = None,
        tool_context=None,
        use_native_tool_calls: bool | None = None,
    ):
        """流式处理入口(委托 StreamRunner,行为不变)。"""
        from .stream_runner import StreamRunner

        yield from StreamRunner(self).stream(
            user_query,
            conversation_history=conversation_history,
            tool_context=tool_context,
            use_native_tool_calls=use_native_tool_calls,
        )
