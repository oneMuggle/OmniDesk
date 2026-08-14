"""任务 1(P0)+ 前端契约:LLM 失败不落库、log_id 输出、orchestrator error 标记。

覆盖:
- 同步接口:失败响应不新建会话 / 不追加消息,但仍写 AgentLog(tool_success=False),
  响应携带 error=true 与 log_id
- SSE 流:失败时 done/session 事件携带 error=true,不落库,session 事件携带 log_id
- 显式 error 标记缺失时,按"回答生成失败"前缀兜底判定
- orchestrator.process / process_stream 返回显式 error 标记;失败回答不进缓存
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from smart_assistant.agent.orchestrator import AgentOrchestrator
from smart_assistant.models import AgentLog, SmartAssistantSession


# =============================================================================
# 工具函数
# =============================================================================


def _process_result(answer, error=False, usage=None, fallback=False, intent="general_chat"):
    """构造 AgentOrchestrator.process 的 mock 返回值。"""
    return {
        "answer": answer,
        "intent": intent,
        "tool_used": None,
        "tool_result": None,
        "sources": None,
        "usage": usage,
        "error": error,
        "tool_fallback": fallback,
    }


def _stream_events(answer, error=False, intent="general_chat", include_error_key=True):
    """构造 AgentOrchestrator.process_stream 的 mock SSE 事件流。"""
    done = {"type": "done"}
    if include_error_key:
        done["error"] = error
    events = [
        {
            "type": "meta",
            "intent": intent,
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "tool_fallback": False,
        },
        {"type": "chunk", "content": answer},
        done,
    ]
    return (f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events)


def _parse_sse_events(raw: str) -> list:
    """把 SSE 文本流解析为事件 dict 列表。"""
    events = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if block.startswith("data: "):
            events.append(json.loads(block[6:]))
    return events


# =============================================================================
# 同步接口:失败不落库
# =============================================================================


@pytest.mark.django_db
class TestCreateFailureNoPersistence:
    """POST /api/smart-assistant/chat/ 失败路径。"""

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_failure_without_cid_does_not_create_session(self, mock_cls, admin_client):
        """无 conversation_id 且 LLM 失败时:不新建会话,仍写 AgentLog。"""
        mock_cls.return_value.process.return_value = _process_result(
            "回答生成失败: 连接超时", error=True
        )
        sessions_before = SmartAssistantSession.objects.count()

        resp = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "你好"},
            format="json",
        )

        assert resp.status_code == 200
        data = resp.json()
        # 错误响应仍返回给前端展示
        assert data["error"] is True
        assert data["answer"].startswith("回答生成失败")
        assert data["conversation_id"] is None
        # 前端契约:log_id 存在
        assert isinstance(data["log_id"], int)
        # 不新建会话
        assert SmartAssistantSession.objects.count() == sessions_before
        # AgentLog 仍写入(审计),tool_success=False,session 为空
        log = AgentLog.objects.get(id=data["log_id"])
        assert log.tool_success is False
        assert log.session is None
        assert log.user_query == "你好"

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_failure_with_cid_does_not_append_messages(
        self, mock_cls, admin_client, admin_user_obj
    ):
        """有 conversation_id 且 LLM 失败时:不追加消息,日志关联原会话。"""
        session = SmartAssistantSession.objects.create(
            user=admin_user_obj,
            title="已有会话",
            messages=[
                {"role": "user", "content": "首问"},
                {"role": "assistant", "content": "首答"},
            ],
            turn_count=1,
        )
        mock_cls.return_value.process.return_value = _process_result(
            "回答生成失败: 模型不可用", error=True
        )

        resp = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "续问", "conversation_id": session.id},
            format="json",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is True
        assert data["conversation_id"] == session.id
        # 消息未被污染
        session.refresh_from_db()
        assert len(session.messages) == 2
        assert session.turn_count == 1
        # 审计日志关联原会话
        log = AgentLog.objects.get(id=data["log_id"])
        assert log.session_id == session.id
        assert log.tool_success is False

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_failure_prefix_detection_without_explicit_flag(self, mock_cls, admin_client):
        """orchestrator 未带 error 标记时,按回答前缀兜底判定失败。"""
        result = _process_result("回答生成失败: 未知异常")
        del result["error"]  # 模拟旧版 orchestrator 无显式标记
        mock_cls.return_value.process.return_value = result
        sessions_before = SmartAssistantSession.objects.count()

        resp = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "前缀兜底"},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.json()["error"] is True
        assert SmartAssistantSession.objects.count() == sessions_before

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_success_persists_and_returns_log_id(self, mock_cls, admin_client):
        """成功路径:正常落库,响应 error=false 且携带 log_id。"""
        mock_cls.return_value.process.return_value = _process_result("正常回答")

        resp = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "成功路径"},
            format="json",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is False
        assert isinstance(data["log_id"], int)
        session = SmartAssistantSession.objects.get(id=data["conversation_id"])
        assert len(session.messages) == 2
        log = AgentLog.objects.get(id=data["log_id"])
        assert log.session_id == session.id
        assert log.tool_success is True


# =============================================================================
# SSE 流:失败不落库
# =============================================================================


@pytest.mark.django_db
class TestStreamFailureNoPersistence:
    """POST /api/smart-assistant/chat/stream/ 失败路径。"""

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_stream_failure_without_cid_no_session(self, mock_cls, admin_client):
        """流式失败且无 cid:不新建会话,session 事件带 error 与 log_id。"""
        mock_cls.return_value.process_stream.return_value = _stream_events(
            "回答生成失败: 流中断", error=True
        )
        sessions_before = SmartAssistantSession.objects.count()

        resp = admin_client.post(
            "/api/smart-assistant/chat/stream/",
            {"query": "流式失败"},
            format="json",
        )
        raw = b"".join(resp.streaming_content).decode("utf-8")
        events = _parse_sse_events(raw)

        # done 事件携带 error=true
        done = next(e for e in events if e["type"] == "done")
        assert done["error"] is True
        # session 事件携带 error 与 log_id
        session_evt = next(e for e in events if e["type"] == "session")
        assert session_evt["error"] is True
        assert session_evt["conversation_id"] is None
        assert isinstance(session_evt["log_id"], int)
        # 不新建会话
        assert SmartAssistantSession.objects.count() == sessions_before
        # AgentLog 仍写入
        log = AgentLog.objects.get(id=session_evt["log_id"])
        assert log.tool_success is False
        assert log.session is None

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_stream_failure_with_cid_no_append(self, mock_cls, admin_client, admin_user_obj):
        """流式失败且有 cid:不追加消息,日志关联原会话。"""
        session = SmartAssistantSession.objects.create(
            user=admin_user_obj,
            title="已有会话",
            messages=[
                {"role": "user", "content": "首问"},
                {"role": "assistant", "content": "首答"},
            ],
            turn_count=1,
        )
        mock_cls.return_value.process_stream.return_value = _stream_events(
            "回答生成失败: 超时", error=True
        )

        resp = admin_client.post(
            "/api/smart-assistant/chat/stream/",
            {"query": "续问", "conversation_id": session.id},
            format="json",
        )
        raw = b"".join(resp.streaming_content).decode("utf-8")
        events = _parse_sse_events(raw)

        session_evt = next(e for e in events if e["type"] == "session")
        assert session_evt["error"] is True
        assert session_evt["conversation_id"] == session.id

        session.refresh_from_db()
        assert len(session.messages) == 2
        log = AgentLog.objects.get(id=session_evt["log_id"])
        assert log.session_id == session.id
        assert log.tool_success is False

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_stream_prefix_fallback_without_done_error_key(self, mock_cls, admin_client):
        """done 事件无 error 键时,按回答前缀兜底判定,仍不落库。"""
        mock_cls.return_value.process_stream.return_value = _stream_events(
            "回答生成失败: 旧版事件流", include_error_key=False
        )
        sessions_before = SmartAssistantSession.objects.count()

        resp = admin_client.post(
            "/api/smart-assistant/chat/stream/",
            {"query": "兜底判定"},
            format="json",
        )
        raw = b"".join(resp.streaming_content).decode("utf-8")
        events = _parse_sse_events(raw)

        session_evt = next(e for e in events if e["type"] == "session")
        assert session_evt["error"] is True
        assert SmartAssistantSession.objects.count() == sessions_before

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_stream_success_creates_session_with_log_id(self, mock_cls, admin_client):
        """流式成功:创建会话,session 事件携带 log_id 且 error=false。"""
        mock_cls.return_value.process_stream.return_value = _stream_events("流式成功回答")

        resp = admin_client.post(
            "/api/smart-assistant/chat/stream/",
            {"query": "流式成功"},
            format="json",
        )
        raw = b"".join(resp.streaming_content).decode("utf-8")
        events = _parse_sse_events(raw)

        session_evt = next(e for e in events if e["type"] == "session")
        assert session_evt["error"] is False
        assert isinstance(session_evt["log_id"], int)
        session = SmartAssistantSession.objects.get(id=session_evt["conversation_id"])
        assert session.messages[-1]["content"] == "流式成功回答"
        log = AgentLog.objects.get(id=session_evt["log_id"])
        assert log.session_id == session.id
        assert log.tool_success is True


# =============================================================================
# SSE 流:生成器中途异常的失败收口与审计
# =============================================================================


@pytest.mark.django_db
class TestStreamMidStreamExceptionAudit:
    """process_stream 生成器中途抛异常:流必须完整收尾且失败必审计。

    模拟 DB/工具异常逃逸出 orchestrator 的场景:已 yield 部分 chunk 后抛
    RuntimeError。view 层必须按失败路径收口——补发失败 chunk/done、写
    AgentLog(tool_success=False)、发 session 事件,且失败不落库。
    """

    @staticmethod
    def _broken_stream(*args, **kwargs):
        """先吐 meta + 部分 chunk,再抛 RuntimeError 模拟异常逃逸。"""
        events = [
            {
                "type": "meta",
                "intent": "general_chat",
                "tool_used": None,
                "tool_result": None,
                "sources": None,
                "tool_fallback": False,
            },
            {"type": "chunk", "content": "部分内容"},
        ]
        for event in events:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        raise RuntimeError("模拟 DB/工具异常逃逸")

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_mid_stream_exception_no_cid_completes_and_audits(self, mock_cls, admin_client):
        """无 cid 中途异常:流完整收尾(done/session 齐全),审计落库,不新建会话。"""
        mock_cls.return_value.process_stream.side_effect = self._broken_stream
        sessions_before = SmartAssistantSession.objects.count()

        resp = admin_client.post(
            "/api/smart-assistant/chat/stream/",
            {"query": "中途异常"},
            format="json",
        )
        raw = b"".join(resp.streaming_content).decode("utf-8")
        events = _parse_sse_events(raw)

        # 补发的失败 chunk 与已 streamed 的部分内容都在流中
        chunk_contents = [e.get("content", "") for e in events if e["type"] == "chunk"]
        assert any("部分内容" in content for content in chunk_contents)
        assert any("[错误] 回答生成失败" in content for content in chunk_contents)
        # 补发的 done 事件携带 error 与输出契约的 kind/hint
        done = next(e for e in events if e["type"] == "done")
        assert done["error"] is True
        assert "kind" in done and "hint" in done
        # session 事件正常发出
        session_evt = next(e for e in events if e["type"] == "session")
        assert session_evt["error"] is True
        assert session_evt["conversation_id"] is None
        assert isinstance(session_evt["log_id"], int)

        # 失败不落库语义保持:不新建会话
        assert SmartAssistantSession.objects.count() == sessions_before
        # AgentLog 写入且 tool_success=False,session 为空
        log = AgentLog.objects.get(id=session_evt["log_id"])
        assert log.tool_success is False
        assert log.session is None
        # 审计内容:失败前缀 + 已累积的部分内容
        assert log.llm_response.startswith("[错误] 回答生成失败")
        assert "部分内容" in log.llm_response

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_mid_stream_exception_with_cid_no_append(
        self, mock_cls, admin_client, admin_user_obj
    ):
        """有 cid 中途异常:不追加消息,审计日志关联原会话。"""
        session = SmartAssistantSession.objects.create(
            user=admin_user_obj,
            title="已有会话",
            messages=[
                {"role": "user", "content": "首问"},
                {"role": "assistant", "content": "首答"},
            ],
            turn_count=1,
        )
        mock_cls.return_value.process_stream.side_effect = self._broken_stream

        resp = admin_client.post(
            "/api/smart-assistant/chat/stream/",
            {"query": "续问", "conversation_id": session.id},
            format="json",
        )
        raw = b"".join(resp.streaming_content).decode("utf-8")
        events = _parse_sse_events(raw)

        done = next(e for e in events if e["type"] == "done")
        assert done["error"] is True
        session_evt = next(e for e in events if e["type"] == "session")
        assert session_evt["error"] is True
        assert session_evt["conversation_id"] == session.id

        # 消息未被部分内容污染
        session.refresh_from_db()
        assert len(session.messages) == 2
        assert session.turn_count == 1
        log = AgentLog.objects.get(id=session_evt["log_id"])
        assert log.session_id == session.id
        assert log.tool_success is False


# =============================================================================
# orchestrator error 标记
# =============================================================================


class TestOrchestratorErrorFlag:
    """AgentOrchestrator 显式 error 标记与失败回答不缓存。"""

    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.ToolRegistry")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_general_answer")
    def test_process_error_true_on_llm_failure(
        self, mock_general, mock_classify, mock_registry, mock_plan
    ):
        """通用对话路径 LLM 失败时 result['error'] 为 True。"""
        mock_plan.return_value = []
        mock_classify.return_value = "general_chat"
        mock_registry.get_tool.return_value = None
        mock_registry.get_all_schemas.return_value = []
        mock_general.return_value = ("回答生成失败: 所有端点不可用", None)

        result = AgentOrchestrator().process("你好")

        assert result["error"] is True
        assert result["answer"].startswith("回答生成失败")

    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.ToolRegistry")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_general_answer")
    def test_process_error_false_on_success(
        self, mock_general, mock_classify, mock_registry, mock_plan
    ):
        """成功回答时 result['error'] 为 False。"""
        mock_plan.return_value = []
        mock_classify.return_value = "general_chat"
        mock_registry.get_tool.return_value = None
        mock_registry.get_all_schemas.return_value = []
        mock_general.return_value = ("你好,我是助手。", None)

        result = AgentOrchestrator().process("你好")

        assert result["error"] is False

    @patch("smart_assistant.agent.orchestrator.cache_answer")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.ToolRegistry")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_answer")
    def test_failed_answer_not_cached(
        self, mock_generate, mock_classify, mock_registry, mock_plan, mock_cache
    ):
        """工具路径 LLM 失败时 error=True 且不写入回答缓存。"""
        mock_plan.return_value = []
        mock_classify.return_value = "schedule_query"
        mock_tool = MagicMock()
        mock_tool.name = "schedule_query"
        mock_tool.execute.return_value = {"found": True, "schedules": []}
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{"name": "schedule_query", "description": "t"}]
        mock_generate.return_value = ("回答生成失败: 模型超时", None)

        result = AgentOrchestrator().process("明天谁值班?")

        assert result["error"] is True
        mock_cache.assert_not_called()

    @patch("smart_assistant.agent.orchestrator.cache_answer")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.ToolRegistry")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_answer")
    def test_success_answer_still_cached(
        self, mock_generate, mock_classify, mock_registry, mock_plan, mock_cache
    ):
        """成功回答仍正常写入缓存(回归保护)。"""
        mock_plan.return_value = []
        mock_classify.return_value = "schedule_query"
        mock_tool = MagicMock()
        mock_tool.name = "schedule_query"
        mock_tool.require_confirmation = False  # L1.1 fix:ConfirmationHook 全局注册后 MagicMock 隐式恒真,需显式关闭
        mock_tool.execute.return_value = {"found": True, "schedules": []}
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{"name": "schedule_query", "description": "t"}]
        mock_generate.return_value = ("明天张三值班。", None)

        result = AgentOrchestrator().process("明天谁值班?")

        assert result["error"] is False
        mock_cache.assert_called_once()

    @pytest.mark.django_db
    @patch("smart_assistant.agent.stream_runner.generate_tool_chain_plan")
    @patch("smart_assistant.agent.stream_runner.ToolRegistry")
    @patch("smart_assistant.agent.stream_runner.classify_intent")
    @patch("smart_assistant.agent.stream_runner.generate_general_answer")
    def test_stream_done_carries_error_on_failure(
        self, mock_general, mock_classify, mock_registry, mock_plan
    ):
        """流式通用对话失败时 done 事件携带 error=true。

        注:输出契约升级后,失败 done 事件会经 classify_error_kind 追加
        kind/hint,该判定需查询 LlmAppConfig,故本用例需要 django_db。
        """
        mock_plan.return_value = []
        mock_classify.return_value = "general_chat"
        mock_registry.get_tool.return_value = None
        mock_registry.get_all_schemas.return_value = []
        mock_general.return_value = ("回答生成失败: 流式失败", None)

        chunks = list(AgentOrchestrator().process_stream("你好"))

        assert mock_general.call_count == 1
        last = json.loads(chunks[-1].split("data: ", 1)[1])
        assert last["type"] == "done"
        assert last["error"] is True

    @patch("smart_assistant.agent.stream_runner.generate_tool_chain_plan")
    @patch("smart_assistant.agent.stream_runner.ToolRegistry")
    @patch("smart_assistant.agent.stream_runner.classify_intent")
    @patch("smart_assistant.agent.stream_runner.generate_answer_stream")
    def test_stream_done_error_false_on_success(
        self, mock_stream, mock_classify, mock_registry, mock_plan
    ):
        """流式工具路径成功时 done 事件 error=false。"""
        mock_plan.return_value = []
        mock_classify.return_value = "schedule_query"
        mock_tool = MagicMock()
        mock_tool.name = "schedule_query"
        mock_tool.require_confirmation = False  # L1.1 fix:ConfirmationHook 全局注册后 MagicMock 隐式恒真,需显式关闭
        mock_tool.execute.return_value = {"found": True, "schedules": []}
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [{"name": "schedule_query", "description": "t"}]
        mock_stream.return_value = iter(["你好", "世界"])

        chunks = list(AgentOrchestrator().process_stream("问题"))

        assert mock_stream.call_count == 1
        last = json.loads(chunks[-1].split("data: ", 1)[1])
        assert last["type"] == "done"
        assert last["error"] is False


# =============================================================================
# SSE 流:DB 写阶段异常兜底(修复 B)与 last_error 契约(修复 A)
# =============================================================================


@pytest.mark.django_db
class TestStreamPersistGuard:
    """DB 写阶段(session.create / AgentLog.create)异常:view 外层兜底必须
    yield fallback done,让前端 reader.read() 正常收到 EOF —— 否则连接被
    Django 异常关闭,vite 代理不转发 EOF,前端 UI 永久卡在"取消"状态。
    """

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_session_create_exception_yields_fallback_done(self, mock_cls, admin_client):
        """SmartAssistantSession.objects.create 抛异常 → 流仍完整收尾(fallback done)。"""
        sessions_before = SmartAssistantSession.objects.count()
        mock_cls.return_value.process_stream.return_value = _stream_events("成功回答")
        with patch(
            "smart_assistant.views.chat.SmartAssistantSession.objects.create",
            side_effect=RuntimeError("db unavailable"),
        ):
            resp = admin_client.post(
                "/api/smart-assistant/chat/stream/",
                {"query": "持久化失败"},
                format="json",
            )
            # 关键断言:join 不 raise —— 修复 B 前 generator 异常会在此炸掉测试
            raw = b"".join(resp.streaming_content).decode("utf-8")

        events = _parse_sse_events(raw)
        # orchestrator 原生 done(error=False) 在前,DB 写失败后兜底 done(error=True)
        # 在后 —— 断言最后一个事件是兜底 done,流以错误收尾且连接正常关闭
        last = events[-1]
        assert last["type"] == "done"
        assert last["error"] is True
        assert "kind" in last  # 携带错误分类,前端可精确展示而非通用提示
        # 日志未写成 → 无 session 事件(log_id 无从生成)
        assert not any(e["type"] == "session" for e in events)
        assert SmartAssistantSession.objects.count() == sessions_before

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_agentlog_create_exception_yields_fallback_done(self, mock_cls, admin_client):
        """AgentLog.objects.create 抛异常 → 同样兜底收尾(会话已建,日志缺失)。"""
        sessions_before = SmartAssistantSession.objects.count()
        mock_cls.return_value.process_stream.return_value = _stream_events("成功回答")
        with patch(
            "smart_assistant.views.chat.AgentLog.objects.create",
            side_effect=RuntimeError("log write failed"),
        ):
            resp = admin_client.post(
                "/api/smart-assistant/chat/stream/",
                {"query": "日志失败"},
                format="json",
            )
            raw = b"".join(resp.streaming_content).decode("utf-8")

        events = _parse_sse_events(raw)
        last = events[-1]
        assert last["type"] == "done"
        assert last["error"] is True
        assert not any(e["type"] == "session" for e in events)
        # 会话先于日志创建,兜底优先保证流收尾(审计缺失是已知权衡)
        assert SmartAssistantSession.objects.count() == sessions_before + 1

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_stream_success_last_error_is_empty_string(self, mock_cls, admin_client):
        """修复 A:流式成功创建会话显式传 last_error='',不依赖 PostgreSQL 端 default。"""
        mock_cls.return_value.process_stream.return_value = _stream_events("成功回答")
        resp = admin_client.post(
            "/api/smart-assistant/chat/stream/",
            {"query": "成功"},
            format="json",
        )
        raw = b"".join(resp.streaming_content).decode("utf-8")
        events = _parse_sse_events(raw)
        session_evt = next(e for e in events if e["type"] == "session")
        session = SmartAssistantSession.objects.get(id=session_evt["conversation_id"])
        assert session.last_error == ""
