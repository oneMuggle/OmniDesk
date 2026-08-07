"""L1 原生 Function Calling 端到端测试(spec §6.3,8 个用例)。

通过进程内 mock LLM 服务(:mod:`mock_llm_server`) + 真实 HTTP 往返,
覆盖「视图 → 编排器(tool_calls 主循环) → 路由器 → mock LLM → 工具执行 →
自然语言回答 → AgentLog 决策日志落库」全链路,完全不依赖真实 LLM/网络。

覆盖场景(对应 spec §6.3 表格):
1. test_e2e_happy_path_single_tool          — LLM 调 1 个工具 → 第二轮自然语言回答
2. test_e2e_two_tools_parallel              — LLM 1 轮调 2 个工具(并行)→ 总结
3. test_e2e_invalid_arguments_lmm_recovers  — arguments JSON 不合法 → 注入 invalid_arguments → LLM 重试
4. test_e2e_unauthorized_tool_blocked       — LLM 调到未注册工具 → 注入 unavailable → LLM 换工具
5. test_e2e_max_rounds_fallback             — LLM 永远返回 tool_calls → 3 轮后强制 tool_choice=none → 兜底回答
6. test_e2e_json_path_fallback              — USE_NATIVE_TOOL_CALLS=False → AgentLog.tool_call_path=="json"
7. test_e2e_streaming_with_tool_calls       — SSE 路径对 tool_calls 能力查询保持完整事件流 + finish_reason
8. test_e2e_decision_log_persisted          — AgentLog.tool_calls_meta 含 round/tool/arguments/duration_ms

关键隔离措施:
- Ollama 兜底指向空端口(127.0.0.1:9),保证失败路径不依赖本机环境;
- 每个测试前后清空 ``llm_service.router._routers`` 单例缓存。
"""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.test import override_settings

from llm_service.router import LLMRouter, get_router
from smart_assistant.models import AgentLog, LlmAppConfig, LlmEndpoint

CHAT_URL = "/api/smart-assistant/chat/"
STREAM_URL = "/api/smart-assistant/chat/stream/"

# 非零单价:150 tokens × 0.02 元/千token = 0.003 元(供 cost 断言)
COST_PER_1K = Decimal("0.02")
MOCK_MODEL = "mock-model"

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _disable_tool_timeout_guard(settings):
    """本 E2E 文件内关闭线程化工具超时熔断。

    原因:``TimeoutGuardHook.run_guarded_sync`` 把工具执行放进 worker 线程,
    而测试用 ``:memory:`` SQLite 的共享缓存跨连接访问会抛
    ``OperationalError: database table is locked``。关闭后工具在请求线程内
    同步执行,与 DB 连接同线程,数据可见。超时熔断语义由
    ``test_hooks_wiring.py`` 单测单独覆盖,不影响本文件验证目标。
    """
    settings.SMART_ASSISTANT_TOOL_TIMEOUT_ENABLED = False
    yield


@pytest.fixture(autouse=True)
def _isolate_llm_routing(monkeypatch):
    """隔离外部 LLM 依赖 + 清理 router 单例缓存(每个测试独立)。

    - Ollama 兜底地址指向 127.0.0.1:9(discard 端口,无监听 → 立即
      ConnectionRefused),失败降级路径在任何机器上都确定性失败;
    - 清空按 app_name 缓存的 router 单例,避免上一个测试(或本测试
      回滚掉的事务数据)残留在 ``LLMRouter._configs`` 中。
    """
    import llm_service.router as router_mod

    monkeypatch.setattr(LLMRouter, "OLLAMA_BASE", "http://127.0.0.1:9")
    router_mod._routers.clear()
    yield
    router_mod._routers.clear()


@pytest.fixture()
def mock_llm():
    """进程内 mock LLM 服务(端口 0 自动分配,退出即停线程)。"""
    from smart_assistant.tests.mock_llm_server import running_server

    with running_server() as service:
        yield service


@pytest.fixture()
def native_llm_config(mock_llm):
    """DB 中建立指向 mock 服务、声明 native_tool_calls 能力的端点配置。

    ``model_capabilities=[{"native_tool_calls": True}]`` 是 L1 端到端
    走原生 tool_calls 路径的必要条件(orchestrator._endpoint_supports_tool_calls)。
    """
    endpoint = LlmEndpoint.objects.create(
        name="mock 端点",
        api_endpoint=mock_llm.url,
        api_key="sk-mock-test",
        is_active=True,
        priority=1,
        cost_per_1k_tokens=COST_PER_1K,
        model_capabilities=[{"native_tool_calls": True}],
    )
    LlmAppConfig.objects.create(
        app_name="smart_assistant",
        endpoint=endpoint,
        model_name=MOCK_MODEL,
        is_active=True,
    )
    get_router("smart_assistant").refresh()
    return SimpleNamespace(endpoint=endpoint, mock=mock_llm)


@pytest.fixture()
def schedule_fixture():
    """明天排班记录:让 schedule_query 工具在原生路径下真正命中数据。"""
    from datetime import timedelta

    from django.utils import timezone
    from events.models import Schedule
    from personnel.models import Personnel

    person = Personnel.objects.create(name="张三", department="研发部")
    Schedule.objects.create(
        duty_date=timezone.now().date() + timedelta(days=1),
        duty_person=person,
        duty_leader=person,
    )
    return person


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _parse_sse_events(raw: str) -> list:
    """把 SSE 原始文本解析为事件字典列表(仅取 data: 行)。"""
    events = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block.startswith("data: "):
            continue
        events.append(json.loads(block[len("data: ") :]))
    return events


# ---------------------------------------------------------------------------
# 1. happy path:LLM 调 1 个工具 → 后端执行 → 第二轮自然语言回答
# ---------------------------------------------------------------------------


def test_e2e_happy_path_single_tool(admin_client, native_llm_config, schedule_fixture):
    """'明天排班' → 第一轮 tool_calls(schedule_query)→ 工具执行 → 第二轮自然语言回答。"""
    resp = admin_client.post(CHAT_URL, {"query": "明天排班"}, format="json")

    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] is False
    # 第二轮 mock 自然语言回答(确定性文本)
    assert "早班" in data["answer"] or "张三" in data["answer"]
    assert data["tool_call_path"] == "native"
    assert data["tool_used"] == "schedule_query"
    assert data["tool_calls_rounds"] == 1
    assert len(data["tool_calls_meta"]) == 1
    assert data["tool_calls_meta"][0]["tool"] == "schedule_query"


# ---------------------------------------------------------------------------
# 2. two tools parallel:LLM 1 轮调 2 个工具 → 2 个 tool 消息 → 总结
# ---------------------------------------------------------------------------


def test_e2e_two_tools_parallel(admin_client, native_llm_config):
    """'本周安排' → 第一轮同时调 schedule_query + memo_query → 第二轮总结。"""
    resp = admin_client.post(CHAT_URL, {"query": "本周安排"}, format="json")

    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] is False
    assert data["tool_call_path"] == "native"
    assert data["tool_calls_rounds"] == 1
    assert len(data["tool_calls_meta"]) == 2
    tools = {entry["tool"] for entry in data["tool_calls_meta"]}
    assert tools == {"schedule_query", "memo_query"}


# ---------------------------------------------------------------------------
# 3. invalid arguments:arguments 非 JSON → 注入 invalid_arguments → LLM 重试
# ---------------------------------------------------------------------------


def test_e2e_invalid_arguments_lmm_recovers(admin_client, native_llm_config):
    """第一轮 arguments 非法 → orchestrator 注入 invalid_arguments → LLM 第二轮修正。"""
    resp = admin_client.post(CHAT_URL, {"query": "乱码参数"}, format="json")

    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] is False
    assert data["tool_call_path"] == "native"
    assert data["tool_calls_rounds"] == 2
    meta = data["tool_calls_meta"]
    assert len(meta) == 2
    assert meta[0]["tool"] == "schedule_query"
    assert meta[0]["error"] == "invalid_args"
    # 第二轮 LLM 给出合法参数,工具成功执行(无 error 键)
    assert meta[1]["tool"] == "schedule_query"
    assert "error" not in meta[1]
    assert data["answer"]


# ---------------------------------------------------------------------------
# 4. unauthorized:LLM 调到未注册/无权工具 → 注入 unavailable → LLM 换工具
# ---------------------------------------------------------------------------


def test_e2e_unauthorized_tool_blocked(admin_client, native_llm_config):
    """第一轮调到未注册工具 → 注入 tool_unavailable_for_user → LLM 第二轮换合法工具。"""
    resp = admin_client.post(CHAT_URL, {"query": "管理员操作"}, format="json")

    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] is False
    assert data["tool_call_path"] == "native"
    meta = data["tool_calls_meta"]
    assert len(meta) == 2
    assert meta[0]["error"] == "unavailable"
    assert meta[0]["tool"] == "admin_only_tool"
    # LLM 换工具:第二轮调用已注册的 schedule_query 且执行成功
    assert meta[1]["tool"] == "schedule_query"
    assert "error" not in meta[1]
    assert data["answer"]


# ---------------------------------------------------------------------------
# 5. max rounds fallback:LLM 永远返回 tool_calls → 3 轮后强制 tool_choice=none
# ---------------------------------------------------------------------------


def test_e2e_max_rounds_fallback(admin_client, native_llm_config):
    """mock 永远返回 tool_calls → 3 轮后 orchestrator 强制 tool_choice=none → 兜底回答。"""
    resp = admin_client.post(CHAT_URL, {"query": "永远查询"}, format="json")

    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] is False
    assert data["tool_call_path"] == "native"
    assert data["tool_calls_rounds"] == 3
    assert len(data["tool_calls_meta"]) == 3
    # 兜底回答非空(强制 tool_choice=none 后 mock 返回固定文本)
    assert data["answer"]


# ---------------------------------------------------------------------------
# 6. JSON 路径 fallback:旧端点(无 tool_calls 能力)→ AgentLog.tool_call_path=="json"
# ---------------------------------------------------------------------------


@override_settings(USE_NATIVE_TOOL_CALLS=False)
def test_e2e_json_path_fallback(admin_client, native_llm_config):
    """强制关闭 native 开关 → orchestrator 走 JSON 路径 → AgentLog.tool_call_path=='json'。"""
    resp = admin_client.post(CHAT_URL, {"query": "明天排班"}, format="json")

    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_call_path"] == "json"
    assert data["tool_calls_rounds"] == 0
    assert data["tool_calls_meta"] == []

    log = AgentLog.objects.get(user_query="明天排班")
    assert log.tool_call_path == "json"
    assert log.tool_calls_rounds == 0
    assert log.tool_calls_meta == []


# ---------------------------------------------------------------------------
# 7. 流式:SSE 路径对 tool_calls 能力查询保持完整事件流 + done 带 finish_reason
# ---------------------------------------------------------------------------


def test_e2e_streaming_with_tool_calls(admin_client, native_llm_config):
    """'/chat/stream/' 对 tool_calls 场景查询 → meta → chunk → done → session,完成回答。"""
    resp = admin_client.post(STREAM_URL, {"query": "明天排班"}, format="json")

    assert resp.status_code == 200
    raw = b"".join(resp.streaming_content).decode("utf-8")
    events = _parse_sse_events(raw)
    types = [e["type"] for e in events]

    assert len(types) >= 4
    assert types[0] == "meta"
    assert types[-2:] == ["done", "session"]
    assert all(t == "chunk" for t in types[1:-2])
    assert len(types[1:-2]) >= 1

    done = events[-2]
    assert done["error"] is False
    # done 帧携带 finish_reason,供前端判定回答结束
    assert done["finish_reason"] == "stop"

    chunk_text = "".join(e["content"] for e in events if e["type"] == "chunk")
    assert chunk_text  # 最终回答非空

    session_evt = events[-1]
    assert session_evt["error"] is False
    assert isinstance(session_evt["log_id"], int)
    assert AgentLog.objects.filter(user_query="明天排班").exists()


# ---------------------------------------------------------------------------
# 8. 决策日志:AgentLog.tool_calls_meta 含 round/tool/arguments/duration_ms
# ---------------------------------------------------------------------------


def test_e2e_decision_log_persisted(admin_client, native_llm_config, schedule_fixture):
    """chat 后查 AgentLog.tool_calls_meta 每轮含 round/tool/arguments/duration_ms。"""
    resp = admin_client.post(CHAT_URL, {"query": "明天排班"}, format="json")
    assert resp.status_code == 200

    log = AgentLog.objects.get(user_query="明天排班")
    assert log.tool_call_path == "native"
    assert log.tool_calls_rounds == 1
    meta = log.tool_calls_meta
    assert len(meta) == 1
    entry = meta[0]
    # spec §6.3 契约:round / tool / arguments / duration_ms 四键齐备
    assert "round" in entry and entry["round"] == 0
    assert entry["tool"] == "schedule_query"
    assert "arguments" in entry and isinstance(entry["arguments"], dict)
    assert "duration_ms" in entry and isinstance(entry["duration_ms"], int)
