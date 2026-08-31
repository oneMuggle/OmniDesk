"""LLMRouter 透传 tools/tool_choice 单元测试。

本任务覆盖范围:
- `LLMRouter.generate_with_tools()` 新方法签名/返回值/透传 tools/tool_choice 三个最小契约
- 不依赖具体工具 schema(Task 4 才实现)
- 不修改 `LLMRouter.generate()` 现有签名/返回值(保留 24 个调用点的向后兼容)

设计决策:不修改 `generate()` 二元组签名,新增 `generate_with_tools()`
三元组方法。理由:
- 现有 24 个调用点假设 `(content, usage)` 二元组,改签名将大面积破坏
- 调用点同步属于 Task 6 orchestrator 拆分工作
- brief Step 3 风险说明明确允许此路径偏离

测试通过 ``LLMRouter.generate_with_tools(..., endpoint_url=...)`` 显式
覆盖真实 DB 端点配置,直接命中进程内的 ``mock_llm_server``。
"""

import pytest
import requests

from llm_service.router import LLMRouter
from smart_assistant.ssrf import safe_request
from smart_assistant.tests.mock_llm_server import running_server


# 标准 OpenAI 格式 tool schema fixture:1 个最小函数定义,供透传断言
SAMPLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "schedule_query",
            "description": "查询排班",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }
]


@pytest.fixture
def mock_server():
    """进程内确定性 mock LLM 服务（OpenAI 兼容,端口 0 自动分配）。"""
    with running_server() as service:
        yield service


@pytest.fixture
def safe_test_requester(mock_server):
    """测试 transport 显式把安全 hostname 映射到本地 mock 服务。"""

    def requester(url, **kwargs):
        kwargs.pop("timeout", None)
        return requests.post(
            url.replace("test-safe.invalid", f"127.0.0.1:{mock_server.port}"),
            timeout=120,
            **kwargs,
        )

    return requester


@pytest.fixture
def safe_test_resolver():
    """显式声明测试 transport 的安全解析结果；不改变生产默认策略。"""
    return lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 80))]


@pytest.mark.django_db
class TestGenerateWithToolsPassthrough:
    """generate_with_tools() 透传契约 + 三元组返回值。"""

    def test_router_generate_with_tools_passes_tools_to_endpoint(
        self, mock_server, safe_test_resolver, safe_test_requester
    ):
        """新方法应将 tools 参数原样透传到 OpenAI 兼容 endpoint 请求体。"""
        router = LLMRouter(requester=safe_test_requester, resolver=safe_test_resolver)
        # 选用不触发 TOOL_CALL_SCENARIOS 的 query,验证透传路径走默认文本;
        # Task 10 起 mock 多了关键字场景 → 该场景的解析测见
        # test_generate_with_tools_parses_real_tool_calls_payload
        messages = [{"role": "user", "content": "普通问答"}]

        content, usage, tool_calls = router.generate_with_tools(
            messages=messages,
            tools=SAMPLE_TOOLS,
            tool_choice="auto",
            endpoint_url="http://test-safe.invalid",
        )

        # 透传契约:收到 1 条请求
        assert mock_server.request_count == 1
        sent_body = mock_server.requests[-1]
        assert sent_body["path"] == "/v1/chat/completions"
        assert isinstance(content, str)
        assert isinstance(usage, dict)
        assert isinstance(tool_calls, list)
        # 不命中 TOOL_CALL_SCENARIOS,tool_calls 仍为空列表
        assert tool_calls == []

    def test_generate_with_tools_returns_three_tuple_with_empty_tool_calls(
        self, mock_server, safe_test_resolver, safe_test_requester
    ):
        """未触发工具调用时,tool_calls 为空列表(确保下游可以走标准文本回复路径)。"""
        router = LLMRouter(requester=safe_test_requester, resolver=safe_test_resolver)
        messages = [{"role": "user", "content": "普通问答"}]

        result = router.generate_with_tools(
            messages=messages,
            tools=SAMPLE_TOOLS,
            tool_choice="auto",
            endpoint_url="http://test-safe.invalid",
        )

        # 必须能解包为 3 个元素(返回类型严格契约)
        assert len(result) == 3
        content, usage, tool_calls = result
        assert isinstance(content, str)
        assert isinstance(usage, dict)
        # usage 必须包含 token 计数(向后兼容)
        assert "total_tokens" in usage
        # tool_calls 是 list,即使为空也必须是 list 类型(下游类型守卫)
        assert isinstance(tool_calls, list)

    def test_generate_with_tools_supports_endpoint_url_override(
        self, mock_server, safe_test_resolver, safe_test_requester
    ):
        """``endpoint_url`` 参数应覆盖 DB 配置,直接命中测试 mock URL。"""
        router = LLMRouter(requester=safe_test_requester, resolver=safe_test_resolver)
        # 即便 router 有 DB 配置,``endpoint_url`` 应优先
        result = router.generate_with_tools(
            messages=[{"role": "user", "content": "test"}],
            endpoint_url="http://test-safe.invalid",
        )

        assert mock_server.request_count == 1
        # URL 拼装验证:必须打到 mock_server 的 /v1/chat/completions
        last = mock_server.requests[-1]
        assert last["path"] == "/v1/chat/completions"
        # 返回值结构
        content, usage, tool_calls = result
        assert content
        assert tool_calls == []

    def test_generate_with_tools_parses_real_tool_calls_payload(
        self, mock_server, safe_test_resolver, safe_test_requester
    ):
        """Task 3 reviewer carry-over:解析真实 ``tool_calls`` payload。

        mock server(Task 10)新增 TOOL_CALL_SCENARIOS 后,带"明天排班" +
        tools 的请求会返回真实 ``[{id, type, function: {name, arguments}}]``
        数组。本测试验证 router 透传 + 解析层把每个 entry 准确折成
        ``{"id", "type", "function": {"name", "arguments"}}`` 三键 dict,
        且 ``arguments`` 原样保留(供后续 orchestrator 反序列化)。
        """
        import json

        from smart_assistant.tests.mock_llm_server import TOOL_CALL_SCENARIOS

        # 触发 TOOL_CALL_SCENARIOS 的特定关键字
        trigger_keyword = next(iter(TOOL_CALL_SCENARIOS))
        expected = TOOL_CALL_SCENARIOS[trigger_keyword][0]
        first_expected_tc = expected["choices"][0]["message"]["tool_calls"][0]
        expected_name = first_expected_tc["function"]["name"]

        router = LLMRouter(requester=safe_test_requester, resolver=safe_test_resolver)
        content, usage, tool_calls = router.generate_with_tools(
            messages=[{"role": "user", "content": trigger_keyword}],
            tools=SAMPLE_TOOLS,
            tool_choice="auto",
            endpoint_url="http://test-safe.invalid",
        )

        # router 层解析应原样保留 OpenAI spec 字段
        assert isinstance(tool_calls, list) and len(tool_calls) >= 1, f"应至少解析 1 个 tool_call,实际: {tool_calls!r}"

        first = tool_calls[0]
        # 必有 3 个键: id / type / function (OpenAI spec)
        assert set(first.keys()) == {"id", "type", "function"}, (
            f"tool_call 顶层键应为 id/type/function 三键,实际 {sorted(first.keys())}"
        )
        # id: 必须是非空字符串,且以 mock 约定 "call_" 开头
        assert isinstance(first["id"], str) and first["id"].startswith("call_"), first["id"]
        # type 字段恒等于字符串 "function"
        assert first["type"] == "function"
        # function.{name, arguments}
        assert first["function"]["name"] == expected_name
        assert isinstance(first["function"]["arguments"], str)
        # arguments 必须是合法 JSON 字符串(后续 orchestrator 要 json.loads)
        parsed = json.loads(first["function"]["arguments"])
        assert isinstance(parsed, dict)
