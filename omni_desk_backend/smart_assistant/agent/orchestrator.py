import json
import logging
import time
import uuid

from django.conf import settings

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
    set_confirmation_draft,
)
from .tool_chain_planner import generate_tool_chain_plan
from .tool_chain_executor import (
    execute_tool_chain,
    synthesize_answer as synthesize_chain_answer,
    ToolChainExecutor,
)
from .result_synthesizer import ResultSynthesizer
from ..hooks.base import Reject
from ..hooks.wiring import (
    apply_failure_hooks,
    apply_post_execute_hooks,
    apply_pre_execute_hooks,
    execute_guarded,
)


logger = logging.getLogger(__name__)


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


def _dict_to_query(validated) -> str:
    """把原生 tool_calls 的 validated 参数 dict 拆包为 ``execute()`` 期望的 query 字符串。

    F1 修复(2026-08-07):orchestrator 此前把 LLM 返回的 ``validated``(dict,
    来自 ``json.loads(tc.function.arguments)``)直接传给
    ``execute_with_guard(query, context)``,而 ``BaseTool.execute`` 签名期望
    ``query: str`` —— 导致:

    - **崩溃(6 工具)**:memo / document / project / sensor / news / personnel
      内部对 query 调 ``replace()`` / ``strip()``,dict 无该方法抛
      ``AttributeError``;
    - **静默错乱(5+ 工具)**:schedule / event / meeting_room 等 ``"X" in query``
      变成查 dict 的 key,恒为 ``False``(查错日期);compliance / external_link
      迭代 dict 得到 key 而非查询词。

    拆包策略:
    - **优先取 ``query`` 字段** —— 所有 19 个工具的 OpenAI schema 均以
      ``query`` 为必填自然语言输入,execute 实现只消费 query;LLM 额外给出的
      结构化字段(schedule 的 date_from/date_to、personnel 的 department 等)
      不拼接进 query(保留 F1 防污染决策,避免污染关键词匹配如 memo 的
      title__icontains),而是由 ``_execute_native_tool`` 经 ``params``
      完整透传给工具,工具 opt-in 读取,缺失时回退 query 解析;
    - **无 ``query`` 时兜底** —— 把其余非 query 字段序列化为
      ``key: value`` 片段(``，`` 连接),保留 LLM 提供的结构化参数语义;
    - 非 dict 输入(理论不出现)直接 ``str()`` 化,保持调用方不挂起。

    JSON fallback 路径(``_legacy_process``)仍传原始 ``user_query`` 字符串,
    本函数仅作用于原生 tool_calls 路径,不影响 A/B 对等。
    """
    if isinstance(validated, str):
        return validated
    if not isinstance(validated, dict):
        return "" if validated is None else str(validated)
    query = validated.get("query")
    if query is not None and str(query).strip():
        return str(query)
    parts = []
    for key, value in validated.items():
        if key == "query" or value is None:
            continue
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        parts.append(f"{key}: {value}")
    return "，".join(parts) if parts else ""


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
                    and (
                        user_is_staff
                        or bool(getattr(settings, "USE_NATIVE_TOOL_CALLS_FOR_ALL", False))
                    )
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
                    llm_messages = self._build_initial_messages(
                        query, tool_context, conversation_history
                    )
                content, usage, meta = self._process_tool_calls_path(
                    query=query, context=tool_context, llm_messages=llm_messages
                )
                return self._wrap_native_to_dict(content, usage, meta)
            except Exception as exc:
                # 降级策略:新路径异常 → JSON 路径兜底
                logger.warning(
                    "tool_calls 路径异常,降级到 JSON 路径: %s", exc, exc_info=True
                )
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
                        context={"history": conversation_history or [], "dry_run": True},
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
                # 非 confirmation_required 的 Reject 或其他情况:走既有路径
                # (apply_pre_execute_hooks 内部已做失败降级,透传 params)
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
                cached_answer = get_cached_answer(
                    user_query, intent, context_sig=scope_sig, tool_call_path="json"
                )
                if cached_answer:
                    answer = cached_answer
                    usage = None
                else:
                    answer, usage = generate_answer(user_query, intent, tool.name, tool_result, conversation_history)
                    # 失败响应不进缓存,避免错误文本被后续请求反复命中
                    if not is_failed_answer(answer):
                        cache_answer(
                            user_query, intent, answer, context_sig=scope_sig, tool_call_path="json"
                        )
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

    # === 原生 tool_calls 路径的单个工具执行(Final review fix wave) ===

    def _execute_native_tool(self, tool, validated: dict, context) -> tuple[dict, dict | None, dict | None]:
        """原生 tool_calls 路径的单个工具执行(修 C-1 + C-2,2026-08-07)。

        对齐 ``_legacy_process`` 的 scope-aware 执行 + 完整 hook 链,替代此前
        直接 ``tool.execute_with_guard(_dict_to_query(validated), context)``:

        - **C-1(越权/跨 scope 泄漏)**:``supports_scope_filter`` 工具经
          ``build_base_queryset`` + ``get_queryset_for_scope`` 派生 scoped
          queryset,再 ``execute_guarded(tool, params, scope, qs, context)``
          执行 —— 确保 SELF/DEPARTMENT/GLOBAL 三级 scope 生效(此前完全跳过
          scope 分支,staff 用户能查到他人数据,已实证 Alice 查 Bob 的 memo)。
        - **C-2(Hook 系统绕过)**:与 legacy 路径一致的 hook 链 ——
          ``require_confirmation`` 工具先经 ``apply_pre_execute_hooks`` 拦截
          (``Reject(confirmation_required)`` → dry_run → 存 draft → 返回
          awaiting_confirmation);执行失败经 ``apply_failure_hooks``;输出统一
          经 ``apply_post_execute_hooks``(PII 脱敏)。此前只走
          ``execute_with_guard``(仅 TimeoutGuardHook),PII 掩码不生效、写工具
          永远拿不到 confirm-replay。

        返回 ``(result, confirmation, failure)``:
            result: 工具输出 dict(post hook 之后;失败时为 failure-hook 结构化兜底)
            confirmation: ``None`` 或 ``{"token": ..., "draft": ...}`` ——
                工具标记需要用户二次确认时返回,调用方应立即终止本轮并透传
                awaiting_confirmation + confirmation_token 给前端。
            failure: ``None`` 或 ``{"error": "execution_failed", "detail": ...}`` ——
                执行抛异常时返回,供调用方写入 tool_calls_meta 审计(与
                F1-era 契约一致,失败工具在审计轨迹中可见)。
        """
        query = _dict_to_query(validated)
        # I-2:透传完整 validated 字典作为 params,LLM 提供的结构化字段
        # (date_from / chunk_index / department / limit / …)到达工具。
        # query 仍是自然语言主输入(不拼接进 query,保留 F1 防污染决策);
        # 结构化字段经 params 显式传递,工具 opt-in 读取,缺失时回退 query 解析。
        params = validated if isinstance(validated, dict) else {"query": query}
        hook_ctx = context if context is not None else {}

        # C-2:require_confirmation 工具先走 pre-hook 确认拦截(与 legacy 对齐)
        if getattr(tool, "require_confirmation", False):
            hook_result = apply_pre_execute_hooks(tool, hook_ctx, {"query": query})
            if isinstance(hook_result, Reject) and hook_result.error_code == "confirmation_required":
                dry_run_context = {
                    "history": [],
                    "dry_run": True,
                    "user": getattr(context, "user", None),
                }
                dry_run_result = execute_guarded(tool, query, context=dry_run_context)
                draft = dry_run_result.get("draft") if isinstance(dry_run_result, dict) else None
                if not draft:
                    return (
                        {
                            "found": False,
                            "message": f"工具 {tool.name} 标记为需要确认,但未返回预演结果(draft),请联系管理员",
                        },
                        None,
                        None,
                    )
                token = str(uuid.uuid4())
                set_confirmation_draft(
                    token,
                    {
                        "tool_name": tool.name,
                        "user_query": query,
                        "context_sig": _scope_cache_sig(context),
                        "draft": draft,
                    },
                )
                return {"found": True, "draft": draft}, {"token": token, "draft": draft}, None
            # 非 confirmation_required 的 Reject / 无 pre-hook:走既有执行路径

        failure: dict | None = None
        try:
            # C-1:scope-aware 执行分支(与 _legacy_process 的 414-423 一致)
            if context is not None and getattr(tool, "supports_scope_filter", False):
                base_qs = tool.build_base_queryset()
                scoped_qs = tool.get_queryset_for_scope(base_qs, context)
                result = execute_guarded(
                    tool,
                    params=params,
                    scope=context.scope,
                    qs=scoped_qs,
                    context=context,
                )
            else:
                result = execute_guarded(tool, query=query, params=params, context=context)
        except Exception as exc:
            # C-2:ON_FAILURE 钩子链(与 legacy 一致):结构化 fallback 优先
            failure = {"error": "execution_failed", "detail": str(exc)}
            recovery = apply_failure_hooks(tool, exc, hook_ctx)
            if recovery.action == "fallback" and isinstance(recovery.fallback_value, dict):
                result = recovery.fallback_value
            else:
                result = {"found": False, "message": f"工具执行失败: {str(exc)}"}
        # C-2:POST_EXECUTE 钩子链(PII 脱敏,统一出口)
        result = apply_post_execute_hooks(tool, result, hook_ctx)
        return result, None, failure

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
        """原生 tool_calls 工具轮(F2 抽取,2026-08-09)。

        - 最多 ``settings.MAX_TOOL_CALLS_ROUNDS`` 轮(默认 3);
        - 每轮 ``router.generate_with_tools(messages, tools, tool_choice='auto')``;
        - 工具错误 4 类:
            * invalid_arguments(JSON 不合法 / schema 校验失败)
            * tool_unavailable_for_user(get_tool_for_user 返回 None)
            * tool_timeout(execute_with_guard 抛 TimeoutError;归类为 execution_failed)
            * execution_failed(任意其他异常)
        - 3 轮后强制 ``tool_choice="none"``;
        - confirm-replay 工具提前返回 awaiting_confirmation。

        返回:
            ``(content, usage, meta, tool_round_messages)``
            - content: 最终答案文本(confirm-replay 时为 draft summary;
              JSON 降级时为 JSON 路径答案)
            - meta: 含 tool_calls_meta / tool_calls_rounds / tool_call_path,
              confirm-replay 时含 awaiting_confirmation / confirmation_token / draft
            - tool_round_messages: 工具结果已 append、未含最终答案轮的
              messages(供流式最终轮复用)
        """
        from smart_assistant.agent.tool_context_resolver import resolve_tools_for_user

        # 注入 user 参数(required_auth 工具对未登录用户不可见)
        tools_schema = resolve_tools_for_user(context.user)
        tool_calls_meta: list = []
        rounds = 0
        max_rounds = int(getattr(settings, "MAX_TOOL_CALLS_ROUNDS", 3))

        for round_idx in range(max_rounds):
            try:
                content, usage, tool_calls = self.router.generate_with_tools(
                    messages=llm_messages,
                    tools=tools_schema,
                    tool_choice="auto",
                )
            except Exception as exc:
                # 降级策略(来自 Task 3 reviewer):新方法异常 → 走 JSON 路径
                logger.warning(
                    "generate_with_tools 异常,降级到 _process_json_path: %s", exc, exc_info=True
                )
                content, usage, meta = self._process_json_path(
                    query=query, context=context, llm_messages=llm_messages
                )
                return content, usage, meta, llm_messages

            if not tool_calls:
                # LLM 主动选择不调工具,直接返回 content;llm_messages 为
                # 工具轮状态(未含本轮 content),供流式最终轮复用。
                return content, usage, {
                    "tool_calls_meta": tool_calls_meta,
                    "tool_calls_rounds": rounds,
                    "tool_call_path": "native",
                }, llm_messages

            rounds += 1
            tool_results = []

            for tc in tool_calls:
                t0 = time.monotonic()
                func_name = tc.get("function", {}).get("name", "")
                tool_call_id = tc.get("id", "")

                # 1) 工具可用性:required_auth / 匿名用户 / 不存在 → unavailable
                tool = ToolRegistry.get_tool_for_user(func_name, context.user)
                if tool is None:
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(
                                {"error": "tool_unavailable_for_user"},
                                ensure_ascii=False,
                            ),
                        }
                    )
                    tool_calls_meta.append(
                        {
                            "round": round_idx,
                            "tool": func_name,
                            "error": "unavailable",
                            "duration_ms": 0,
                        }
                    )
                    continue

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
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(
                                {"error": "invalid_arguments", "detail": str(exc)},
                                ensure_ascii=False,
                            ),
                        }
                    )
                    tool_calls_meta.append(
                        {
                            "round": round_idx,
                            "tool": func_name,
                            "error": "invalid_args",
                            "duration_ms": 0,
                        }
                    )
                    continue

                # 3) 工具执行:统一经 _execute_native_tool(scope-aware + 完整 hook 链)。
                # C-1:supports_scope_filter 工具复用 build_base_queryset +
                #      get_queryset_for_scope 分支,确保 SELF/DEPARTMENT/GLOBAL
                #      scope 生效(此前 execute_with_guard 直接跑全量表,跨用户泄漏)。
                # C-2:pre(post/failure hook 链 + confirm-replay 在 helper 内统一处理,
                #      PII 脱敏不再被绕过。
                try:
                    result, confirmation, failure = self._execute_native_tool(
                        tool, validated, context
                    )
                except Exception as exc:
                    # helper 内部已收口执行异常;此处兜底防御意外异常
                    tool_results.append(
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
                        }
                    )
                    tool_calls_meta.append(
                        {
                            "round": round_idx,
                            "tool": func_name,
                            "error": "execution_failed",
                            "duration_ms": 0,
                        }
                    )
                    continue

                # 工具执行失败(helper 已 apply_failure_hooks):审计轨迹保留 error 标记
                if failure is not None:
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                    tool_calls_meta.append(
                        {
                            "round": round_idx,
                            "tool": func_name,
                            "error": failure.get("error", "execution_failed"),
                            "duration_ms": int((time.monotonic() - t0) * 1000),
                        }
                    )
                    continue

                # confirm-replay:工具标记需要用户二次确认 → 立即终止本轮,
                # 把 awaiting_confirmation + token 透传给视图层(前端再带
                # token 重放执行)。不回灌给 LLM,避免把确认流程当成工具失败。
                if confirmation is not None:
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    tool_calls_meta.append(
                        {
                            "round": round_idx,
                            "tool": func_name,
                            "arguments": validated,
                            "duration_ms": duration_ms,
                        }
                    )
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

                duration_ms = int((time.monotonic() - t0) * 1000)
                tool_calls_meta.append(
                    {
                        "round": round_idx,
                        "tool": func_name,
                        "arguments": validated,
                        "duration_ms": duration_ms,
                    }
                )
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

            # 把 assistant(tool_calls) + tool 结果 append 到 messages
            llm_messages.append(
                {
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": tool_calls,
                }
            )
            llm_messages.extend(tool_results)

        # 3 轮后兜底:强制 tool_choice="none"
        content, usage, _ = self.router.generate_with_tools(
            messages=llm_messages,
            tools=tools_schema,
            tool_choice="none",
        )
        return content, usage, {
            "tool_calls_meta": tool_calls_meta,
            "tool_calls_rounds": rounds,
            "tool_call_path": "native",
        }, llm_messages

    def _process_stream_tool_calls_path(
        self,
        *,
        query: str,
        context,
        llm_messages: list,
    ):
        """F2: 原生 tool_calls 流式路径(缓冲工具轮 + 流式最终轮)。

        - 复用 ``_run_tool_calls_rounds``(与 ``_process_tool_calls_path`` 对称);
        - confirm-replay → yield awaiting_confirmation + confirmation_token;
        - 无工具轮(rounds==0,含 JSON 降级)→ 单 chunk 输出缓冲 content;
        - 有工具轮(rounds>0)→ ``router.generate(messages=tool_round_messages,
          stream=True)`` 重生成流式最终答案(真打字动画)。
        """
        try:
            content, usage, meta, tool_round_messages = self._run_tool_calls_rounds(
                query=query, context=context, llm_messages=llm_messages
            )
        except Exception as exc:
            content = f"回答生成失败: {exc}"
            meta = {"tool_call_path": "native", "tool_calls_rounds": 0}
            tool_round_messages = llm_messages

        # confirm-replay:立即透传给前端,不走最终轮
        if meta.get("awaiting_confirmation"):
            tool_calls_meta = meta.get("tool_calls_meta", [])
            tool_used = tool_calls_meta[-1].get("tool", "") if tool_calls_meta else ""
            draft = meta.get("draft", {})
            yield sse_event(
                {
                    "type": "meta",
                    "intent": "tool_call",
                    "tool_used": tool_used,
                    "tool_result": {"draft": draft},
                }
            )
            yield sse_event(
                {
                    "type": "confirmation",
                    "awaiting_confirmation": True,
                    "confirmation_token": meta["confirmation_token"],
                    "draft": draft,
                    "answer": content or "请确认以下操作",
                }
            )
            yield sse_event({"type": "done", "error": False, "awaiting_confirmation": True})
            return

        # 输出契约:非确认场景先发 meta(前端依赖首个事件为 meta 渲染意图/工具)。
        # 与 confirm-replay 分支的 meta(intent="tool_call") 保持一致;JSON 降级
        # 时透传其 intent,便于前端展示。
        tool_calls_meta = meta.get("tool_calls_meta") or []
        tool_used = (
            tool_calls_meta[0].get("tool")
            if tool_calls_meta and isinstance(tool_calls_meta[0], dict)
            else None
        )
        yield sse_event(
            {
                "type": "meta",
                "intent": meta.get("intent", "tool_call"),
                "tool_used": tool_used,
                "tool_result": None,
            }
        )

        rounds = meta.get("tool_calls_rounds", 0)
        if rounds > 0:
            # 流式最终轮:重生成(真打字动画)。tool_round_messages 以工具结果
            # 收尾,LLM 基于工具结果产出最终自然语言答案。
            stream_parts = []
            try:
                stream = self.router.generate(messages=tool_round_messages, stream=True)
                for chunk in stream:
                    stream_parts.append(chunk)
                    yield sse_event({"type": "chunk", "content": chunk})
            except Exception as exc:
                stream_parts = [content or f"回答生成失败: {exc}"]
                yield sse_event({"type": "chunk", "content": stream_parts[0]})
            full_answer = "".join(stream_parts)
        else:
            # 首轮即无 tool_calls / JSON 降级:直接输出缓冲 content 单 chunk
            full_answer = content or ""
            yield sse_event({"type": "chunk", "content": full_answer})

        done = {"type": "done", "finish_reason": "stop", "error": is_failed_answer(full_answer)}
        if done["error"]:
            annotate_error_kind(done, full_answer)
        yield sse_event(done)

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

    def process_stream(
        self,
        user_query: str,
        conversation_history: list = None,
        tool_context=None,
        use_native_tool_calls: bool | None = None,
    ):
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

            # Task 7 of feat/sa-office-files:process_stream 在路径决策之前
            # 短路,使用 tool_call_path="none" 作为"未决路径"维度,避免与
            # legacy/原生路径的缓存互相污染。
            cached_answer = get_cached_answer(
                user_query, intent, context_sig=scope_sig, tool_call_path="none"
            )
            if cached_answer:
                # 缓存命中,直接 yield 完整 answer + done(不动 LLM)
                yield sse_event({"type": "meta", "intent": intent, "cache_hit": True})
                yield sse_event({"type": "chunk", "content": cached_answer})
                done = {"type": "done", "cache_hit": True, "error": is_failed_answer(cached_answer)}
                if done["error"]:
                    annotate_error_kind(done, cached_answer)
                yield sse_event(done)
                return

        # === F2 原生 tool_calls 流式分支(L1.1,2026-08-09) ===
        # 门控与 process() 对称:USE_NATIVE_TOOL_CALLS + 端点能力 + staff/FOR_ALL
        if use_native_tool_calls is None:
            try:
                user_is_staff = bool(
                    tool_context is not None
                    and getattr(tool_context, "user", None) is not None
                    and bool(getattr(tool_context.user, "is_staff", False))
                )
                use_native = (
                    bool(getattr(settings, "USE_NATIVE_TOOL_CALLS", False))
                    and self._endpoint_supports_tool_calls()
                    and (
                        user_is_staff
                        or bool(getattr(settings, "USE_NATIVE_TOOL_CALLS_FOR_ALL", False))
                    )
                )
            except Exception:
                logger.warning("原生流式门控检查失败,走 intent 流程", exc_info=True)
                use_native = False
        else:
            use_native = bool(use_native_tool_calls)

        if use_native:
            from smart_assistant.tools.tool_context import ToolContext
            if tool_context is None:
                tool_context = ToolContext(user=None)
            llm_messages = self._build_initial_messages(
                user_query, tool_context, conversation_history
            )
            try:
                yield from self._process_stream_tool_calls_path(
                    query=user_query, context=tool_context, llm_messages=llm_messages
                )
            except Exception as exc:
                # 兜底:原生流式内部未收口的异常 → 输出失败回答,不崩溃
                logger.warning("原生流式路径异常: %s", exc, exc_info=True)
                yield sse_event({"type": "chunk", "content": f"回答生成失败: {exc}"})
                done = {"type": "done", "finish_reason": "stop", "error": True}
                annotate_error_kind(done, f"回答生成失败: {exc}")
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
            # === confirm-replay 流式拦截(与 process() 对称) ===
            if getattr(tool, "require_confirmation", False):
                hook_ctx = tool_context if tool_context is not None else {"history": conversation_history or []}
                hook_result = apply_pre_execute_hooks(tool, hook_ctx, {"query": user_query})
                if isinstance(hook_result, Reject) and hook_result.error_code == "confirmation_required":
                    dry_run_result = execute_guarded(
                        tool,
                        user_query,
                        context={"history": conversation_history or [], "dry_run": True},
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
                        yield sse_event(done)
                        return
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
                    yield sse_event(
                        {"type": "meta", "intent": intent, "tool_used": tool.name, "tool_result": {"draft": draft}}
                    )
                    yield sse_event(
                        {
                            "type": "confirmation",
                            "awaiting_confirmation": True,
                            "confirmation_token": token,
                            "draft": draft,
                            "answer": draft.get("summary") or "请确认以下操作",
                        }
                    )
                    yield sse_event({"type": "done", "error": False, "awaiting_confirmation": True})
                    return
            # === confirm-replay 流式拦截结束 ===

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

        # 发送结束信号(携带错误标记,供 view 层决定是否落库;
        # finish_reason 供前端判定回答正常收尾)
        full_answer = "".join(stream_parts)
        done = {"type": "done", "finish_reason": "stop", "error": is_failed_answer(full_answer)}
        if done["error"]:
            annotate_error_kind(done, full_answer, tool_used=tool_name, tool_result=tool_result)
        yield sse_event(done)
