"""智能助手 doctor 自检端点 + 后端输出契约测试。

覆盖:
- 访问控制:staff 可访问(200)、非 staff 403、未认证 401
- 各检查项在"无配置/有配置"两种场景下的 status/kind
  (外部探测全部 monkeypatch _probe_http,不发真实网络请求)
- 检查项异常降级:探测函数抛异常也不 500
- 输出契约:同步失败响应含 kind+hint;SSE 事件含 format_version;
  失败 done/session 事件含 kind+hint
- classify_error_kind 判定函数单测(4 种 kind + None)
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from smart_assistant.agent.orchestrator import (
    ERROR_KIND_HINTS,
    AgentOrchestrator,
    classify_error_kind,
)
from smart_assistant.models import KnowledgeDataset, LlmAppConfig, LlmEndpoint

DOCTOR_URL = "/api/smart-assistant/doctor/"
CHAT_URL = "/api/smart-assistant/chat/"
STREAM_URL = "/api/smart-assistant/chat/stream/"

pytestmark = pytest.mark.django_db


# =============================================================================
# 工具函数 / fixtures
# =============================================================================


def _mock_probe(monkeypatch, fail_keywords=(), ok_detail="HTTP 200"):
    """替换 doctor 的 _probe_http:URL 含 fail_keywords 判不可达,其余可达。

    fail_keywords=[""] 时所有 URL 都不可达(空串是任何字符串的子串)。
    """
    from smart_assistant.views import doctor as doctor_mod

    def _fake(url, timeout=3):
        if any(k in url for k in fail_keywords):
            return False, "连接被拒绝（mock）"
        return True, ok_detail

    monkeypatch.setattr(doctor_mod, "_probe_http", _fake)


def _create_llm_config(endpoint_url="http://llm.example.com", active=True):
    """建立 smart_assistant 的 LLM 端点 + 应用配置。"""
    endpoint = LlmEndpoint.objects.create(
        name="主端点",
        api_endpoint=endpoint_url,
        api_key="sk-test",
        is_active=active,
    )
    config = LlmAppConfig.objects.create(
        app_name="smart_assistant",
        endpoint=endpoint,
        model_name="mock-model",
        is_active=active,
    )
    return endpoint, config


def _checks_by_name(response_json):
    return {c["name"]: c for c in response_json["checks"]}


def _parse_sse_events(raw: str) -> list:
    events = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if block.startswith("data: "):
            events.append(json.loads(block[6:]))
    return events


# =============================================================================
# 1. 访问控制
# =============================================================================


class TestDoctorAccessControl:
    """staff 可访问、非 staff 403、未认证 401。"""

    def test_staff_can_access_and_response_shape(self, admin_client, monkeypatch):
        """staff 访问返回 200 + 契约结构（format_version/checked_at/summary/checks）。"""
        _mock_probe(monkeypatch)

        resp = admin_client.get(DOCTOR_URL)

        assert resp.status_code == 200
        data = resp.json()
        assert data["format_version"] == 1
        assert data["checked_at"]
        assert set(data["summary"].keys()) == {"ok", "warn", "error"}
        checks = data["checks"]
        assert isinstance(checks, list) and len(checks) >= 4
        # 每个检查项字段齐全,状态取值合法
        for item in checks:
            assert {"name", "status", "kind", "message", "hint"} <= set(item.keys())
            assert item["status"] in ("ok", "warn", "error")
        # summary 计数与检查项总数一致
        assert sum(data["summary"].values()) == len(checks)

    def test_non_staff_forbidden(self, regular_client, monkeypatch):
        """非 staff 用户返回 403。"""
        _mock_probe(monkeypatch)

        resp = regular_client.get(DOCTOR_URL)

        assert resp.status_code == 403

    def test_unauthenticated_rejected(self, api_client):
        """未认证请求返回 401。"""
        resp = api_client.get(DOCTOR_URL)

        assert resp.status_code == 401


# =============================================================================
# 2. 检查项:无配置 / 有配置场景
# =============================================================================


class TestDoctorChecksNoConfig:
    """空库场景:核心依赖缺失应报 error/warn,且不依赖网络。"""

    def test_empty_config_scene(self, admin_client, monkeypatch):
        """无任何配置:llm_config/llm_endpoints/ragflow 为 error,datasets/ollama/native_tool_calls 为 warn。"""
        _mock_probe(monkeypatch, fail_keywords=[""])  # 所有探测不可达

        data = admin_client.get(DOCTOR_URL).json()
        by_name = _checks_by_name(data)

        assert by_name["llm_config"]["status"] == "error"
        assert by_name["llm_config"]["kind"] == "no_llm_endpoint"
        assert by_name["llm_config"]["hint"]
        assert by_name["llm_endpoints"]["status"] == "error"
        assert by_name["llm_endpoints"]["kind"] == "no_llm_endpoint"
        assert by_name["ollama_fallback"]["status"] == "warn"
        assert by_name["ollama_fallback"]["kind"] == "ollama_unavailable"
        assert by_name["ragflow"]["status"] == "error"
        assert by_name["ragflow"]["kind"] == "ragflow_unavailable"
        assert by_name["datasets"]["status"] == "warn"
        assert by_name["datasets"]["kind"] == "no_active_dataset"
        # 缓存/限流为信息级,恒 ok
        assert by_name["cache_rate_limit"]["status"] == "ok"
        assert by_name["cache_rate_limit"]["kind"] == "info"
        # P1A-2 新增:cache_write_rate_limit(写工具阈值)同为信息级恒 ok
        assert by_name["cache_write_rate_limit"]["status"] == "ok"
        assert by_name["cache_write_rate_limit"]["kind"] == "info"
        # native_tool_calls:空库 → warn/no_llm_endpoint(Task 8 新增)
        assert by_name["native_tool_calls"]["status"] == "warn"
        assert by_name["native_tool_calls"]["kind"] == "no_llm_endpoint"
        # 汇总计数(error 3 + warn 3 + ok 2 = 8 项;原 7 项 + cache_write_rate_limit)
        assert data["summary"]["error"] == 3
        assert data["summary"]["warn"] == 3
        assert data["summary"]["ok"] == 2


class TestDoctorChecksWithConfig:
    """有配置场景:可达 → ok;不可达 → error + 对应 kind。"""

    def test_all_configured_and_reachable(self, admin_client, monkeypatch):
        """配置齐全且全部可达:无 error 项,各检查项均 ok。"""
        from ragflow_service.models import RagflowConfig

        _create_llm_config(endpoint_url="http://llm.example.com")
        RagflowConfig.objects.create(
            name="RAG 主配置",
            api_endpoint="http://ragflow.example.com",
            api_key="k",
            is_active=True,
        )
        KnowledgeDataset.objects.create(name="数据集 1", ragflow_dataset_id="d1", is_active=True)
        _mock_probe(monkeypatch)
        # Task 8:native_tool_calls checker 走 LLMRouter.generate_with_tools,需要 stub 避免真实 HTTP
        monkeypatch.setattr(
            "llm_service.router.LLMRouter.generate_with_tools",
            lambda *args, **kwargs: ("", {}, []),
        )

        data = admin_client.get(DOCTOR_URL).json()
        by_name = _checks_by_name(data)

        assert by_name["llm_config"]["status"] == "ok"
        assert by_name["llm_endpoint:主端点"]["status"] == "ok"
        assert by_name["ollama_fallback"]["status"] == "ok"
        assert by_name["ragflow"]["status"] == "ok"
        assert by_name["datasets"]["status"] == "ok"
        assert by_name["native_tool_calls"]["status"] == "ok"
        assert data["summary"]["error"] == 0

    def test_endpoint_unreachable_is_error(self, admin_client, monkeypatch):
        """有配置但端点不可达:llm_config 仍 ok,端点项 error/llm_unavailable。"""
        _create_llm_config(endpoint_url="http://dead.example.com")
        _mock_probe(monkeypatch, fail_keywords=["dead.example.com"])

        by_name = _checks_by_name(admin_client.get(DOCTOR_URL).json())

        assert by_name["llm_config"]["status"] == "ok"
        item = by_name["llm_endpoint:主端点"]
        assert item["status"] == "error"
        assert item["kind"] == "llm_unavailable"
        assert item["hint"] == ERROR_KIND_HINTS["llm_unavailable"]

    def test_inactive_endpoint_not_probed(self, admin_client, monkeypatch):
        """禁用端点不参与探测;无激活端点时汇总项 llm_endpoints 报 error。"""
        LlmEndpoint.objects.create(
            name="禁用端点",
            api_endpoint="http://off.example.com",
            api_key="sk-test",
            is_active=False,
        )
        _mock_probe(monkeypatch)

        by_name = _checks_by_name(admin_client.get(DOCTOR_URL).json())

        assert "llm_endpoint:禁用端点" not in by_name
        assert by_name["llm_endpoints"]["status"] == "error"
        assert by_name["llm_endpoints"]["kind"] == "no_llm_endpoint"

    def test_ragflow_unreachable(self, admin_client, monkeypatch):
        """Ragflow 配置存在但不可达:error/ragflow_unavailable。"""
        from ragflow_service.models import RagflowConfig

        RagflowConfig.objects.create(
            name="RAG 主配置",
            api_endpoint="http://ragflow.dead.com",
            api_key="k",
            is_active=True,
        )
        _mock_probe(monkeypatch, fail_keywords=["ragflow.dead.com"])

        by_name = _checks_by_name(admin_client.get(DOCTOR_URL).json())

        assert by_name["ragflow"]["status"] == "error"
        assert by_name["ragflow"]["kind"] == "ragflow_unavailable"
        assert by_name["ragflow"]["hint"]

    def test_datasets_zero_warn_active_ok(self, admin_client, monkeypatch):
        """0 个激活数据集 → warn;激活一个后 → ok。"""
        _mock_probe(monkeypatch)

        by_name = _checks_by_name(admin_client.get(DOCTOR_URL).json())
        assert by_name["datasets"]["status"] == "warn"

        KnowledgeDataset.objects.create(name="数据集 X", ragflow_dataset_id="dx", is_active=True)
        by_name = _checks_by_name(admin_client.get(DOCTOR_URL).json())
        assert by_name["datasets"]["status"] == "ok"

    def test_probe_exception_degrades_not_500(self, admin_client, monkeypatch):
        """探测函数抛异常:涉及探测的检查项降级为 internal_error,端点仍 200。"""
        from ragflow_service.models import RagflowConfig
        from smart_assistant.views import doctor as doctor_mod

        def _boom(url, timeout=3):
            raise RuntimeError("探测函数意外异常")

        monkeypatch.setattr(doctor_mod, "_probe_http", _boom)
        # 有 ragflow 配置时 ragflow 检查项也会走探测路径
        RagflowConfig.objects.create(
            name="RAG", api_endpoint="http://r.example.com", is_active=True
        )

        resp = admin_client.get(DOCTOR_URL)

        assert resp.status_code == 200
        by_name = _checks_by_name(resp.json())
        assert by_name["_check_ollama_fallback"]["status"] == "error"
        assert by_name["_check_ollama_fallback"]["kind"] == "internal_error"
        assert by_name["_check_ragflow"]["status"] == "error"


# =============================================================================
# 3. classify_error_kind 判定函数单测
# =============================================================================


class TestClassifyErrorKind:
    """kind 判定规则:ragflow > no_llm_endpoint > llm_unavailable > internal_error。"""

    def test_non_error_returns_none(self):
        """非失败响应返回 None。"""
        assert classify_error_kind({"answer": "正常回答", "error": False}) is None
        assert classify_error_kind({"answer": "正常回答"}) is None

    def test_no_config_returns_no_llm_endpoint(self):
        """空库 + 失败回答 → no_llm_endpoint。"""
        result = {"answer": "回答生成失败: 所有端点不可用", "error": True}

        assert classify_error_kind(result) == "no_llm_endpoint"

    def test_config_exists_returns_llm_unavailable(self):
        """有激活配置但回答失败 → llm_unavailable。"""
        _create_llm_config()
        result = {"answer": "回答生成失败: 模型超时", "error": True}

        assert classify_error_kind(result) == "llm_unavailable"

    def test_inactive_config_counts_as_no_config(self):
        """配置存在但未激活,视同无配置 → no_llm_endpoint。"""
        _create_llm_config(active=False)
        result = {"answer": "回答生成失败: x", "error": True}

        assert classify_error_kind(result) == "no_llm_endpoint"

    def test_knowledge_qa_ragflow_error_takes_priority(self):
        """knowledge_qa + ragflow 错误 → ragflow_unavailable(优先于 LLM 判定)。"""
        _create_llm_config()  # 即使 LLM 配置存在,ragflow 判定优先
        result = {
            "answer": "回答生成失败: 检索失败",
            "error": True,
            "tool_used": "knowledge_qa",
            "tool_result": {
                "found": False,
                "message": "工具执行失败: RagflowClientError: 连接超时",
            },
        }

        assert classify_error_kind(result) == "ragflow_unavailable"

    def test_knowledge_qa_non_ragflow_error_falls_through(self):
        """knowledge_qa 失败但错误与 ragflow 无关 → 按 LLM 配置判定。"""
        result = {
            "answer": "回答生成失败: x",
            "error": True,
            "tool_used": "knowledge_qa",
            "tool_result": {"found": False, "message": "知识库中未找到相关信息"},
        }

        assert classify_error_kind(result) == "no_llm_endpoint"  # 空库

    def test_explicit_error_without_failure_prefix_is_internal(self):
        """显式 error 但回答无失败前缀(有配置)→ internal_error。"""
        _create_llm_config()
        result = {"answer": "自定义业务错误", "error": True}

        assert classify_error_kind(result) == "internal_error"


# =============================================================================
# 4. 输出契约:同步失败响应 kind+hint、SSE format_version
# =============================================================================


class TestSyncFailureContract:
    """POST /chat/ 失败响应:error=true + kind + hint。"""

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_sync_failure_carries_kind_and_hint(self, mock_cls, admin_client):
        """空库失败 → kind=no_llm_endpoint,hint 为契约文案。"""
        mock_cls.return_value.process.return_value = {
            "answer": "回答生成失败: 连接超时",
            "intent": "general_chat",
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "usage": None,
            "error": True,
        }

        data = admin_client.post(CHAT_URL, {"query": "你好"}, format="json").json()

        assert data["error"] is True
        assert data["kind"] == "no_llm_endpoint"
        assert data["hint"] == ERROR_KIND_HINTS["no_llm_endpoint"]

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_sync_success_has_no_kind(self, mock_cls, admin_client):
        """成功响应不携带 kind/hint(保持响应体精简)。"""
        mock_cls.return_value.process.return_value = {
            "answer": "你好,我是助手。",
            "intent": "general_chat",
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "usage": None,
            "error": False,
        }

        data = admin_client.post(CHAT_URL, {"query": "你好"}, format="json").json()

        assert data["error"] is False
        assert "kind" not in data
        assert "hint" not in data


class TestSseContract:
    """SSE 事件契约:所有事件 format_version;失败 done/session 携带 kind+hint。"""

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_stream_failure_session_event_carries_kind_hint(self, mock_cls, admin_client):
        """流式失败:session 事件携带 format_version + kind + hint(ragflow 场景)。"""
        events = [
            {
                "format_version": 1,
                "type": "meta",
                "intent": "knowledge_qa",
                "tool_used": "knowledge_qa",
                "tool_result": {
                    "found": False,
                    "message": "工具执行失败: RagflowClientError: 连接被拒绝",
                },
                "sources": None,
                "tool_fallback": True,
            },
            {"format_version": 1, "type": "chunk", "content": "回答生成失败: 模型不可用"},
            {"format_version": 1, "type": "done", "error": True},
        ]
        mock_cls.return_value.process_stream.return_value = (
            f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events
        )

        resp = admin_client.post(STREAM_URL, {"query": "公司休假制度"}, format="json")
        parsed = _parse_sse_events(b"".join(resp.streaming_content).decode("utf-8"))

        session_evt = next(e for e in parsed if e["type"] == "session")
        assert session_evt["format_version"] == 1
        assert session_evt["error"] is True
        assert session_evt["kind"] == "ragflow_unavailable"
        assert session_evt["hint"] == ERROR_KIND_HINTS["ragflow_unavailable"]

    @patch("smart_assistant.views.chat.AgentOrchestrator")
    def test_stream_success_session_event_has_format_version_no_kind(self, mock_cls, admin_client):
        """流式成功:session 事件携带 format_version,无 kind。"""
        events = [
            {"format_version": 1, "type": "meta", "intent": "general_chat"},
            {"format_version": 1, "type": "chunk", "content": "你好"},
            {"format_version": 1, "type": "done", "error": False},
        ]
        mock_cls.return_value.process_stream.return_value = (
            f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events
        )

        resp = admin_client.post(STREAM_URL, {"query": "你好"}, format="json")
        parsed = _parse_sse_events(b"".join(resp.streaming_content).decode("utf-8"))

        session_evt = next(e for e in parsed if e["type"] == "session")
        assert session_evt["format_version"] == 1
        assert session_evt["error"] is False
        assert "kind" not in session_evt

    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.ToolRegistry")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_general_answer")
    def test_real_orchestrator_failure_events_carry_contract(
        self, mock_general, mock_classify, mock_registry, mock_plan
    ):
        """真实编排器失败事件流:所有事件带 format_version,done 带 kind+hint。"""
        mock_plan.return_value = []
        mock_classify.return_value = "general_chat"
        mock_registry.get_tool.return_value = None
        mock_registry.get_all_schemas.return_value = []
        mock_general.return_value = ("回答生成失败: 所有端点不可用", None)

        chunks = list(AgentOrchestrator().process_stream("你好"))
        events = [
            json.loads(c.split("data: ", 1)[1].rsplit("\n\n", 1)[0]) for c in chunks
        ]

        assert events, "事件流不应为空"
        assert all(e.get("format_version") == 1 for e in events)
        done = events[-1]
        assert done["type"] == "done"
        assert done["error"] is True
        assert done["kind"] == "no_llm_endpoint"  # 空库
        assert done["hint"] == ERROR_KIND_HINTS["no_llm_endpoint"]

    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.ToolRegistry")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    @patch("smart_assistant.agent.orchestrator.generate_answer_stream")
    def test_real_orchestrator_success_done_has_no_kind(
        self, mock_stream, mock_classify, mock_registry, mock_plan
    ):
        """真实编排器成功事件流:chunk 带 format_version,done error=false 且无 kind。"""
        mock_plan.return_value = []
        mock_classify.return_value = "schedule_query"
        mock_tool = MagicMock()
        mock_tool.name = "schedule_query"
        mock_tool.execute.return_value = {"found": True, "schedules": []}
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [
            {"name": "schedule_query", "description": "排班"}
        ]
        mock_stream.return_value = iter(["你好", "世界"])

        chunks = list(AgentOrchestrator().process_stream("问题"))
        events = [
            json.loads(c.split("data: ", 1)[1].rsplit("\n\n", 1)[0]) for c in chunks
        ]

        assert all(e.get("format_version") == 1 for e in events)
        done = events[-1]
        assert done["type"] == "done"
        assert done["error"] is False
        assert "kind" not in done


class TestDoctorWriteRateLimitCheck:
    def setup_method(self):
        from django.core.cache import cache

        cache.clear()

    def test_cache_write_rate_limit_check_present(self, admin_user_obj):
        """doctor 端点应同时报告 chat 与 write-tool 两套限流配置。"""
        from smart_assistant.views.doctor import get_doctor_status

        result = get_doctor_status()
        checks_by_name = {c["name"]: c for c in result["checks"]}
        assert "cache_write_rate_limit" in checks_by_name
        assert checks_by_name["cache_write_rate_limit"]["status"] == "ok"
        assert checks_by_name["cache_write_rate_limit"]["kind"] == "info"
