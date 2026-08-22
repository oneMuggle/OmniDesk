"""结果包装(R5-D5 拆分:orchestrator/result_wrap.py)。

从 orchestrator.py 原样搬运的「JSON dict ↔ (content, usage, meta) 三元组」双向
转换方法,以 ResultWrapMixin 形式供 AgentOrchestrator 继承,行为零变化。

patch 兼容:与 persistence 同理,经 ``persistence._root`` 同源的包根动态解析
读取 patch 目标名(_legacy_process 经 self MRO 命中 LegacyProcessMixin)。
"""

from observability import get_logger

from ..conversation_context import is_failed_answer


logger = get_logger(__name__, "smart_assistant")


def _root():
    """返回 orchestrator 包根模块(patch 目标名的动态解析点)。"""
    from smart_assistant.agent import orchestrator as root_pkg

    return root_pkg


class ResultWrapMixin:
    """原 orchestrator.py 的结果转换方法集(逐字搬运)。"""

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
