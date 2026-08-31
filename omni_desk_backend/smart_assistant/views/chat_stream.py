"""流式聊天路径编排(SSE)——从 views/chat.py 拆分。

职责:stream 入口(前置上下文 → setup → StreamingHttpResponse)
与 SSE 生成器(消费 process_stream → 失败收口 → 流式持久化 → AgentLog → session 事件)。

与 create 路径的关键语义差异(plan §3.4,两套持久化不强行合并):
- 无效会话 id 不返回 404:``prepare_chat_context(require_session=False)``
  静默继续(session=None),无效 cid 的兜底在持久化分支二次 get
  (捕获 DoesNotExist → (None, None))。
- 持久化走 ``_persist_stream_session``(新建会话带 last_error='' 防御),与
  create 版 ``persist_success``(无 last_error 防御)语义有差异。

R5-D3:前置段(serializer 校验 → 附件抽取 → 会话加载 → ToolContext 构造 →
附件注入)收敛为 ``prepare_chat_context`` 单次调用(require_session=False
表达 stream 的"无效会话不 404"语义)。
"""

import json
import time

from django.http import StreamingHttpResponse
from observability import get_logger

from ..agent.conversation_context import (
    FAILED_ANSWER_STREAM_PREFIX,
    apply_rolling_summary,
    count_turns,
    is_failed_answer,
)
from ..agent.orchestrator import (
    ERROR_KIND_HINTS,
    FORMAT_VERSION,
    AgentOrchestrator,
    annotate_error_kind,
    sse_event,
)
from ..cache import public_tool_calls_meta, public_tool_result, safe_public_value, sanitize_public_text, sanitize_public_sources
from ..models import AgentLog, SmartAssistantSession

from .conversation_manager import prepare_chat_context

logger = get_logger(__name__, "smart_assistant")


_STREAM_EVENT_FIELDS = {
    "chunk": {"format_version", "type", "content"},
    "meta": {
        "format_version", "type", "intent", "tool_used", "tool_result", "sources", "tool_fallback",
        "tool_call_path", "tool_calls_meta", "tool_calls_rounds", "cache_hit",
    },
    "done": {
        "format_version", "type", "finish_reason", "error", "awaiting_confirmation", "cache_hit",
        "error_code", "retry_after", "kind", "hint",
    },
    "confirmation": {"format_version", "type", "awaiting_confirmation", "confirmation_token", "draft", "answer"},
}


def _sanitize_stream_event(data):
    """按 SSE 事件类型构造公开 envelope，单独保留可见文本字段。"""
    if not isinstance(data, dict):
        return {}
    event_type = data.get("type")
    if not isinstance(event_type, str):
        return {}
    fields = _STREAM_EVENT_FIELDS.get(event_type)
    if not fields:
        return {}
    public_event = {"type": event_type, "format_version": FORMAT_VERSION}
    for key in fields - {"type", "content", "format_version", "answer"}:
        if key not in data:
            continue
        value = data[key]
        if key in {"confirmation_token", "error_code", "kind", "hint", "finish_reason", "intent", "tool_used"}:
            public_event[key] = sanitize_public_text(value, 200)
        elif key == "tool_result":
            public_event[key] = public_tool_result(value, data.get("tool_used") or "", intent=data.get("intent") or "")
        elif key == "sources":
            public_event[key] = sanitize_public_sources(value)
        else:
            public_event[key] = safe_public_value(value)
    if event_type == "chunk" and "content" in data:
        public_event["content"] = sanitize_public_text(data["content"])
    if event_type == "confirmation" and "answer" in data:
        public_event["answer"] = sanitize_public_text(data["answer"])
    return public_event


def handle_stream_chat(viewset, request) -> StreamingHttpResponse:
    """POST /api/smart-assistant/chat/stream/ 流式路径主体(SSE)。

    ``viewset`` 参数仅用于与 Task 4 委托的调用点保持兼容,本函数内不使用。
    """
    query, tool_context, conversation_history, session, conversation_id, err = prepare_chat_context(
        request,
        # stream 语义:无效会话 id 不返回 404,静默继续流式
        require_session=False,
    )
    if err is not None:
        return err[0]

    start_time = time.time()
    orchestrator = AgentOrchestrator()

    return StreamingHttpResponse(
        _event_stream_generator(
            query=query,
            conversation_id=conversation_id,
            session=session,
            conversation_history=conversation_history,
            tool_context=tool_context,
            orchestrator=orchestrator,
            user=request.user,
            start_time=start_time,
        ),
        content_type="text/event-stream",
    )


def _event_stream_generator(
    *,
    query,
    conversation_id,
    session,
    conversation_history,
    tool_context,
    orchestrator,
    user,
    start_time,
):
    """SSE 事件生成器:消费 process_stream → 失败收口 → 持久化 → session 事件。

    三层 try/兜底语义与 chat.py 原 ``event_stream`` 逐字一致:
    - 内层 try 消费 process_stream(解析与事件累加经 ``_consume_stream_events``);
    - 中途异常补发失败 chunk + 兜底 done;
    - 外层 try 含持久化 + AgentLog + session 事件,异常时兜底固定 internal_error done。
    """
    # 事件状态(由 _consume_stream_events 就地更新;保持原 event_stream 闭包变量语义)
    state = {
        "full_answer": [],
        "meta": {},
        "done_error": False,
        "done_seen": False,
        "stream_error_code": None,
        "stream_retry_after": None,
    }
    stream_exc = None
    # 兜底:DB 写异常也保证前端能收到 done 事件。(历史变量保留,未使用)
    persist_exc = None

    try:
        try:
            for chunk in _consume_stream_events(state, orchestrator, query, conversation_history, tool_context):
                yield chunk
        except Exception as exc:
            # 生成器中途异常(DB/工具异常逃逸):按失败路径收口,保证"失败必审计"——
            # 若直接中断流,前端会把已收到的部分内容当成功回答,且 AgentLog 缺失。
            stream_exc = exc
            state["done_error"] = True
            logger.exception(
                "SSE 流式生成中途异常: conversation_id=%s query_len=%d",
                conversation_id,
                len(query) if isinstance(query, str) else 0,
            )

        partial_answer = "".join(state["full_answer"])
        if stream_exc is not None:
            # 统一采用流式失败前缀,复用 is_failed_answer 语义:
            # 前端失败提示与"失败不落库"逻辑随之自动生效;已累积内容保留进审计记录
            failure_marker = f"{FAILED_ANSWER_STREAM_PREFIX}: 流式生成中断"
            answer = f"{failure_marker}｜已生成部分内容：{partial_answer}" if partial_answer else failure_marker
            # 补发失败 chunk(部分内容此前已 streamed,此处仅补失败标记)
            yield sse_event({"type": "chunk", "content": failure_marker})
            # 生成器未发出 done 时补发携带 kind/hint 的失败 done,让前端完整收尾
            if not state["done_seen"]:
                done_event = {"type": "done", "error": True}
                annotate_error_kind(
                    done_event,
                    answer,
                    tool_used=state["meta"].get("tool_used"),
                    tool_result=state["meta"].get("tool_result"),
                )
                yield sse_event(done_event)
        else:
            answer = partial_answer

        # 失败判定:done 事件显式标记优先,回答前缀兜底
        error = state["done_error"] or is_failed_answer(answer)
        response_time_ms = int((time.time() - start_time) * 1000)

        # 失败响应不落库:无 conversation_id 不新建会话,有则不追加消息
        persist_session = session
        cid = conversation_id
        if not error:
            persist_session, cid = _persist_stream_session(session, conversation_id, query, answer, user)
        elif not conversation_id:
            persist_session = None
            cid = None

        # 失败时仍写 AgentLog(审计需要),tool_success=False
        log = _write_stream_agent_log(
            session=persist_session,
            query=query,
            answer=answer,
            meta=state["meta"],
            response_time_ms=response_time_ms,
            error=error,
        )

        # 输出契约:session 事件携带 format_version;失败时追加 kind + hint
        yield _build_stream_event(
            log,
            cid,
            error,
            answer,
            state["meta"],
            state["stream_error_code"],
            state["stream_retry_after"],
        )
    except Exception as exc:
        # 兜底:DB 写(session.save / AgentLog.create)异常也保证前端能收到 done 事件。
        # 否则前端 reader.read() 永远 pending → UI 永远卡在"取消"状态。
        logger.exception(
            "SSE 流后端持久化异常: conversation_id=%s query_len=%d",
            conversation_id,
            len(query) if isinstance(query, str) else 0,
        )
        # 兜底 done 固定 internal_error:不调用 annotate_error_kind ——
        # 其内部 `_has_active_llm_config()` 会查 DB,若故障恰是 DB 不可达,
        # 兜底自身会再抛 OperationalError → generator 仍无 done → 卡死复现。
        # 也不从 err_answer 推断 kind:真实原因是后端持久化失败,固定文案
        # 比把 DB 问题误报为 LLM/端点问题更能正确引导用户。
        yield sse_event(
            {
                "type": "done",
                "error": True,
                "kind": "internal_error",
                "hint": ERROR_KIND_HINTS["internal_error"],
            }
        )


def _consume_stream_events(state, orchestrator, query, conversation_history, tool_context):
    """消费 process_stream 的 SSE 事件流并就地累加事件状态。

    yield 每条原始 chunk(透传给前端),同时按事件类型更新 ``state``
    (full_answer / meta / done 语义逐字保留 chat.py L376-398)。
    解析失败的非标准 chunk 静默忽略(逐字保留 L386-387)。
    """
    for chunk in orchestrator.process_stream(
        query,
        conversation_history=conversation_history,
        tool_context=tool_context,
    ):
        try:
            payload = chunk.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
            data = json.loads(payload)
        except (IndexError, json.JSONDecodeError):
            continue
        data = _sanitize_stream_event(data)
        if not data:
            continue
        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        event_type = data.get("type")
        if event_type == "chunk":
            state["full_answer"].append(data.get("content", ""))
        elif event_type == "meta":
            state["meta"] = data
        elif event_type == "done":
            state["done_error"] = bool(data.get("error"))
            state["done_seen"] = True
            state["stream_error_code"] = data.get("error_code")
            state["stream_retry_after"] = data.get("retry_after")


def _persist_stream_session(session, conversation_id, query, answer, user):
    """流式路径的成功持久化:已有会话追加消息,无 cid 新建(带 last_error='' 防御)。

    返回 (persist_session, cid)。失败响应不落库的判断在调用方完成。
    注意:与 create 版 ``persist_success`` 语义不同 —— 无效 cid 二次 get 抛
    DoesNotExist → (None, None);新建会话显式 last_error=''(生产事故防御),
    两套实现不强行合并(plan §3.4)。
    """
    if conversation_id:
        try:
            persist_session = SmartAssistantSession.objects.get(id=conversation_id, user=user)
            messages = persist_session.messages or []
            persist_session.messages = messages + [
                {"role": "user", "content": query},
                {"role": "assistant", "content": answer},
            ]
            persist_session.turn_count = count_turns(persist_session.messages)
            if not persist_session.title:
                persist_session.title = query[:50]
            apply_rolling_summary(persist_session)
            persist_session.save()
            cid = conversation_id
        except SmartAssistantSession.DoesNotExist:
            persist_session = None
            cid = None
    else:
        persist_session = SmartAssistantSession.objects.create(
            user=user,
            title=query[:50],
            messages=[
                {"role": "user", "content": query},
                {"role": "assistant", "content": answer},
            ],
            turn_count=1,
            # 防御性:显式传 last_error=''。生产曾因部署镜像内 model 缺
            # 该字段,INSERT 违反 NOT NULL → IntegrityError → generator
            # 异常 → connection 关闭但前端 read() 拿不到 done → UI 卡死。
            # (ORM create 本会应用 model default;显式传保证任何 DB/
            # 迁移状态下都不依赖 default 是否生效。)
            last_error="",
        )
        cid = persist_session.id
    return persist_session, cid


def _write_stream_agent_log(*, session, query, answer, meta, response_time_ms, error):
    """流式路径的 AgentLog 审计写入:失败时 tool_success=False,会话可为空。"""
    return AgentLog.objects.create(
        session=session,
        user_query=sanitize_public_text(query),
        intent=meta.get("intent") or "unknown",
        tool_used=meta.get("tool_used") or "",
        tool_input=safe_public_value({"query": query}),
        tool_output=safe_public_value(meta.get("tool_result") or {}),
        llm_response=sanitize_public_text(answer),
        response_time_ms=response_time_ms,
        # 流式路径暂无 usage 统计,成本留空
        estimated_cost=None,
        tool_success=False if error else (meta.get("tool_fallback") is not True),
        # L1.1 fix(最终 review):流式原生路径决策日志落库,与非流式
        # create(chat.py:285-287)一致;缺省 tool_call_path="intent"
        # (非原生 intent 流程),保持既有审计行为
        tool_call_path=meta.get("tool_call_path") or "intent",
        tool_calls_meta=public_tool_calls_meta(meta.get("tool_calls_meta") or []),
        tool_calls_rounds=meta.get("tool_calls_rounds") or 0,
    )


def _build_stream_event(log, cid, error, answer, meta, stream_error_code, stream_retry_after) -> str:
    """组装 session 事件:携带 format_version;失败时追加 kind + hint。"""
    session_event = {
        "type": "session",
        "format_version": FORMAT_VERSION,
        "conversation_id": cid,
        "log_id": log.id,
        "error": error,
        # P1A-2:透传 RateLimitHook 拒答字段(写工具速率限制)。
        # 缺省 None,前端按通用错误展示,无 breaking。
        "error_code": stream_error_code,
        "retry_after": stream_retry_after,
    }
    if error:
        annotate_error_kind(
            session_event,
            answer,
            tool_used=meta.get("tool_used"),
            tool_result=meta.get("tool_result"),
        )
    return f"data: {json.dumps(session_event, ensure_ascii=False)}\n\n"
