"""智能助手确定性端到端测试：mock LLM 服务 + 真实 HTTP 往返。

与既有 mock ``requests.post`` 的单测不同，本文件不拦截任何 HTTP 层：
DB 中配置 ``LlmEndpoint(api_endpoint=mock 服务地址)`` +
``LlmAppConfig(app_name="smart_assistant")``，让 ``LLMRouter`` 通过
真实 TCP 往返访问进程内的 ``mock_llm_server``，覆盖
「视图 → 编排器 → 路由器 → HTTP → 成本核算 → AgentLog/Session 落库」
全链路，且完全不依赖真实 LLM。

覆盖场景：
1. 正常问答：/chat/ 返回 mock 固定文本，AgentLog 精确核算成本
2. 端点 500：失败回答前缀「回答生成失败」，不建会话，日志照写
3. SSE 流：事件序列 meta → chunk → done → session（子集断言）
4. 重试策略：router 对失败端点**不做同端点重试**，仅降级到下一候选
5. 超时行为：mock 睡眠超过 router 超时阈值 → 全链路失败降级

关键隔离措施（见 _isolate_llm_routing fixture）：
- Ollama 兜底指向空端口（127.0.0.1:9），保证失败路径不依赖本机环境
- 每个测试前后清空 ``llm_service.router._routers`` 单例缓存，
  避免跨测试复用持有过期 DB 配置的 router 实例
"""

import json
import requests
from decimal import Decimal
from types import SimpleNamespace

import pytest

from llm_service.router import LLMRouter, get_router
from smart_assistant.models import (
    AgentLog,
    LlmAppConfig,
    LlmEndpoint,
    SmartAssistantSession,
)
from smart_assistant.tests.mock_llm_server import FIXED_ANSWER, running_server

CHAT_URL = "/api/smart-assistant/chat/"
STREAM_URL = "/api/smart-assistant/chat/stream/"

# 非零单价：150 tokens × 0.02 元/千token = 0.003 元（可精确比对）
COST_PER_1K = Decimal("0.02")
MOCK_MODEL = "mock-model"

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _safe_test_resolver(*args, **kwargs):
    return [(2, 1, 6, "", ("93.184.216.34", 80))]


@pytest.fixture(autouse=True)
def _inject_safe_test_transport(monkeypatch):
    """仅测试显式注入 resolver，生产 safe_request 仍拒绝 loopback。"""
    import llm_service.router as router_mod
    from smart_assistant import ssrf

    def request(method, url, **kwargs):
        kwargs.pop("requester", None)
        kwargs.pop("resolver", None)
        safe_url = url.replace("127.0.0.1", "test-safe.invalid")
        return ssrf.safe_request(
            method,
            safe_url,
            resolver=_safe_test_resolver,
            requester=lambda _checked, **request_kwargs: requests.request(
                method, url, **request_kwargs
            ),
            **kwargs,
        )

    monkeypatch.setattr(router_mod, "safe_request", request)


@pytest.fixture(autouse=True)
def _isolate_llm_routing(monkeypatch):
    """隔离外部 LLM 依赖 + 清理 router 单例缓存（每个测试独立）。

    - Ollama 兜底地址指向 127.0.0.1:9（discard 端口，无监听 →
      立即 ConnectionRefused），失败降级路径在任何机器上都确定性失败；
    - 清空按 app_name 缓存的 router 单例，避免上一个测试（或本测试
      回滚掉的事务数据）残留在 ``LLMRouter._configs`` 中。
    """
    import llm_service.router as router_mod

    monkeypatch.setattr(LLMRouter, "OLLAMA_BASE", "http://127.0.0.1:9")
    router_mod._routers.clear()
    yield
    router_mod._routers.clear()


@pytest.fixture()
def mock_llm():
    """进程内 mock LLM 服务（端口 0 自动分配，退出即停线程）。"""
    with running_server() as service:
        yield service


@pytest.fixture()
def llm_config(mock_llm):
    """DB 中建立指向 mock 服务的 smart_assistant 端点配置。"""
    endpoint = LlmEndpoint.objects.create(
        name="mock 端点",
        api_endpoint=mock_llm.url,
        api_key="sk-mock-test",
        is_active=True,
        priority=1,
        cost_per_1k_tokens=COST_PER_1K,
    )
    config = LlmAppConfig.objects.create(
        app_name="smart_assistant",
        endpoint=endpoint,
        model_name=MOCK_MODEL,
        is_active=True,
    )
    # 让 get_router() 单例重新加载 DB 配置（autouse 已清空缓存，此处显式刷新兜底）
    get_router("smart_assistant").refresh()
    return SimpleNamespace(endpoint=endpoint, config=config)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _parse_sse_events(raw: str) -> list:
    """把 SSE 原始文本解析为事件字典列表（仅取 data: 行）。"""
    events = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block.startswith("data: "):
            continue
        events.append(json.loads(block[len("data: ") :]))
    return events


# ---------------------------------------------------------------------------
# 1. 正常问答
# ---------------------------------------------------------------------------


def test_chat_success_fixed_answer_and_cost(admin_client, llm_config, mock_llm):
    """/chat/ 返回 mock 固定文本，AgentLog 按 150 tokens × 单价精确核算成本。"""
    query = "你好，请介绍一下你自己"

    resp = admin_client.post(CHAT_URL, {"query": query}, format="json")

    assert resp.status_code == 200
    data = resp.json()
    # 子集断言：只查关心的键，容忍未来新增字段
    assert data["error"] is False
    assert data["answer"] == FIXED_ANSWER
    assert data["conversation_id"] is not None
    assert data["log_id"] is not None

    # 成功回答落库：会话 + 日志
    assert SmartAssistantSession.objects.count() == 1
    log = AgentLog.objects.get(user_query=query)
    assert log.session_id == data["conversation_id"]
    assert log.tool_success is True
    assert log.model_name == MOCK_MODEL
    # token 用量来自 mock 的固定 usage（100/50/150）
    assert log.input_tokens == 100
    assert log.output_tokens == 50
    assert log.total_tokens == 150
    # Decimal 精确比对：150 × 0.02 / 1000 = 0.003000
    expected_cost = (Decimal(150) * COST_PER_1K / Decimal(1000)).quantize(Decimal("0.000001"))
    assert log.estimated_cost == expected_cost


# ---------------------------------------------------------------------------
# 2. 端点 500 失败路径
# ---------------------------------------------------------------------------


def test_chat_endpoint_500_failure_no_session(admin_client, llm_config, mock_llm):
    """端点持续 500：失败回答前缀「回答生成失败」，不建会话，日志照写。"""
    query = "这个查询会触发错误"

    resp = admin_client.post(CHAT_URL, {"query": query}, format="json")

    # 视图层始终返回 200，失败语义在 body 的 error 标记
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] is True
    assert data["answer"].startswith("回答生成失败")
    assert data["conversation_id"] is None

    # 失败不落会话，但审计日志照写且 tool_success=False、session 为空
    assert SmartAssistantSession.objects.count() == 0
    log = AgentLog.objects.get(user_query=query)
    assert log.session is None
    assert log.tool_success is False
    assert log.llm_response.startswith("回答生成失败")


# ---------------------------------------------------------------------------
# 3. SSE 流式事件序列
# ---------------------------------------------------------------------------


def test_chat_stream_event_sequence(admin_client, llm_config, mock_llm):
    """/chat/stream/ 事件序列 meta → chunk... → done → session，chunk 拼出固定文本。"""
    query = "流式测试问候"

    resp = admin_client.post(STREAM_URL, {"query": query}, format="json")

    assert resp.status_code == 200
    raw = b"".join(resp.streaming_content).decode("utf-8")
    events = _parse_sse_events(raw)
    types = [e["type"] for e in events]

    # 事件序列：首个 meta、末尾 done + session、中间全是 chunk（至少 1 个）
    assert len(types) >= 4
    assert types[0] == "meta"
    assert types[-2:] == ["done", "session"]
    assert all(t == "chunk" for t in types[1:-2])
    assert len(types[1:-2]) >= 1

    # chunk 内容拼出 mock 固定文本
    chunk_text = "".join(e["content"] for e in events if e["type"] == "chunk")
    assert chunk_text == FIXED_ANSWER

    # 子集断言：meta 只查关心的键（容忍 format_version 等未来新增字段）
    meta = events[0]
    assert "intent" in meta

    done = events[-2]
    assert done["error"] is False

    # session 事件携带 log_id 与 conversation_id
    session_evt = events[-1]
    assert session_evt["error"] is False
    assert isinstance(session_evt["log_id"], int)
    assert isinstance(session_evt["conversation_id"], int)

    # 流式成功同样落库
    assert SmartAssistantSession.objects.count() == 1
    assert AgentLog.objects.filter(user_query=query, tool_success=True).count() == 1


# ---------------------------------------------------------------------------
# 4. 重试策略
# ---------------------------------------------------------------------------


def test_router_no_retry_only_failover(admin_client, llm_config, mock_llm):
    """持续 500 下 mock 请求次数符合 router 策略：每端点仅 1 次，无同端点重试。

    - router 层：单次 generate() 对唯一 DB 端点只发 1 个请求，
      随后降级 Ollama 兜底（已被指向空端口），整体抛异常；
    - 视图层：一次 /chat/ 请求触发编排器的 3 个 LLM 调用点
      （意图分类 + 工具链规划内部分类 + 通用回答生成），
      每个调用点各尝试 mock 恰好 1 次 → 共 3 个请求。
    """
    # --- router 层：单次调用 = 单次请求（无重试）---
    mock_llm.reset()
    with pytest.raises(Exception):
        get_router("smart_assistant").generate(prompt="触发错误")
    assert mock_llm.request_count == 1

    # --- 视图层：3 个 LLM 调用点 × 每点 1 次尝试 = 3 个请求 ---
    mock_llm.reset()
    resp = admin_client.post(CHAT_URL, {"query": "再次触发错误"}, format="json")
    assert resp.json()["error"] is True
    assert mock_llm.request_count == 3


# ---------------------------------------------------------------------------
# 5. 超时行为（mock 的超时关键词路由 + router 超时降级）
# ---------------------------------------------------------------------------


def test_timeout_endpoint_falls_through_to_failure(admin_client, monkeypatch):
    """mock 睡眠超过 router 超时阈值 → ReadTimeout → 全链路失败回答。

    为避免等待 router 默认 120s 超时，monkeypatch 缩小到 1s，
    mock 的 timeout_delay 设为 2s（仍严格超过阈值）。
    """
    monkeypatch.setattr(LLMRouter, "REQUEST_TIMEOUT", 1)

    with running_server(timeout_delay=2.0) as slow_llm:
        endpoint = LlmEndpoint.objects.create(
            name="慢端点",
            api_endpoint=slow_llm.url,
            api_key="sk-mock-slow",
            is_active=True,
            priority=1,
            cost_per_1k_tokens=COST_PER_1K,
        )
        LlmAppConfig.objects.create(
            app_name="smart_assistant",
            endpoint=endpoint,
            model_name=MOCK_MODEL,
            is_active=True,
        )
        get_router("smart_assistant").refresh()

        resp = admin_client.post(CHAT_URL, {"query": "处理超时场景"}, format="json")

        data = resp.json()
        assert data["error"] is True
        assert data["answer"].startswith("回答生成失败")
        assert SmartAssistantSession.objects.count() == 0
        # 每个 LLM 调用点都真实打到了 mock（请求已受理，只是响应太慢）
        assert slow_llm.request_count == 3
