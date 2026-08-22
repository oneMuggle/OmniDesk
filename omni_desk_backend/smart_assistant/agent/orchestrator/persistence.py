"""legacy JSON 路径的执行编排(R5-D5 拆分:orchestrator/persistence.py)。

从 orchestrator.py 原样搬运的「意图分类(缓存优先)→ confirm 拦截 → 工具执行
(超时熔断+钩子链)→ LLM 答案生成(缓存策略)」家族,以 LegacyProcessMixin 形式
供 AgentOrchestrator 继承,行为零变化。
"""

import uuid

from observability import get_logger

from ..conversation_context import is_failed_answer
from ..intent_classifier import (
    classify_intent,
    generate_answer,
    generate_general_answer,
    generate_tool_empty_answer,
)
from ..tool_chain_planner import generate_tool_chain_plan
from ..orchestrator_helpers import _scope_cache_sig
from ..tools.registry import ToolRegistry
from ...cache import (
    get_cached_intent,
    cache_intent,
    get_cached_tool_result,
    cache_tool_result,
    get_cached_answer,
    cache_answer,
    set_confirmation_draft,
)
from ...hooks.base import Reject
from ...hooks.wiring import (
    apply_failure_hooks,
    apply_post_execute_hooks,
    apply_pre_execute_hooks,
    execute_guarded,
)


logger = get_logger(__name__, "smart_assistant")


class LegacyProcessMixin:
    """原 orchestrator.py 的 legacy JSON 路径方法集(逐字搬运)。

    方法解析:AgentOrchestrator(LegacyProcessMixin, ...) 继承后 ``self.*``
    与原单类实现完全一致。
    """

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
        intent = self._classify_legacy_intent(user_query, schemas, conversation_history, has_history, scope_sig)

        # Step 2: 检测是否需要多工具
        tool_chain = generate_tool_chain_plan(user_query, schemas, conversation_history)

        if tool_chain:
            # 多工具链式执行 — Task 17: 走 scope-aware 路径
            return self._process_chain(user_query, tool_chain, conversation_history, tool_context)

        # Step 3: 单工具路由(保持现有路径)
        tool = ToolRegistry.get_tool(intent)
        if tool:
            return self._legacy_single_tool(
                user_query, intent, tool, conversation_history, tool_context, scope_sig, has_history
            )

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

    def _classify_legacy_intent(self, user_query, schemas, conversation_history, has_history, scope_sig):
        """原 _legacy_process 的意图分类段(缓存优先)。"""
        if not has_history:
            cached_intent = get_cached_intent(user_query, schemas, context_sig=scope_sig)
            if cached_intent:
                return cached_intent
            intent = classify_intent(user_query, schemas, conversation_history)
            cache_intent(user_query, schemas, intent, context_sig=scope_sig)
            return intent
        return classify_intent(user_query, schemas, conversation_history)

    def _legacy_confirm_intercept(self, tool, user_query, conversation_history, tool_context, scope_sig, intent):
        """confirm-replay 拦截段(原 _legacy_process 的 confirm 块)。

        返回 dict 表示"已拦截直接返回";返回 None 表示继续正常执行工具。
        """
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
        # === confirm-replay 拦截结束 ===
        return None

    def _legacy_single_tool(self, user_query, intent, tool, conversation_history, tool_context, scope_sig, has_history):
        """原 _legacy_process 的单工具路径:确认拦截 → 执行 → LLM 合成。

        若未命中 confirm-replay 拦截,继续执行工具(经 execute_guarded 超时
        熔断),再走缓存/LLM 合成,返回与 Task 6 前完全对等的 dict。
        """
        hook_ctx = tool_context if tool_context is not None else {"history": conversation_history or []}

        intercepted = self._legacy_confirm_intercept(
            tool, user_query, conversation_history, tool_context, scope_sig, intent
        )
        if intercepted is not None:
            return intercepted

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
        # 行为与原 _legacy_process 的 has_history 分支完全对等:has_history 时
        # 不读缓存、不回写缓存;无历史时先查缓存,miss 才生成并缓存未失败回答。
        cached_answer = (
            get_cached_answer(user_query, intent, context_sig=scope_sig, tool_call_path="json")
            if not has_history
            else None
        )
        if cached_answer:
            answer = cached_answer
            usage = None
        else:
            answer, usage = generate_answer(user_query, intent, tool.name, tool_result, conversation_history)
            # 失败响应不进缓存,避免错误文本被后续请求反复命中
            if not is_failed_answer(answer) and not has_history:
                cache_answer(user_query, intent, answer, context_sig=scope_sig, tool_call_path="json")

        return {
            "answer": answer,
            "intent": intent,
            "tool_used": tool.name,
            "tool_result": tool_result,
            "sources": tool_result.get("sources") if isinstance(tool_result, dict) else None,
            "usage": usage,
            "error": is_failed_answer(answer),
        }
