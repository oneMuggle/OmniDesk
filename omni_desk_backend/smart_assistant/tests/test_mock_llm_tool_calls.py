"""Mock LLM server TOOL_CALL_SCENARIOS 场景测试。

本文件覆盖 Task 10 范围:
- mock server 收到带 ``tools`` 的请求时,按 query 关键字返回预设 tool_calls 响应
- 至少 5 个场景:schedule / personnel / rag / memo / news
- 无 tools 时仍走原有 FIXED_ANSWER keyword 路由(无回归)

设计要点:
- 每个测试独立启停 mock server(:func:`running_server` context manager)
- 只校验 mock 服务响应结构,LLMRouter 透传链路测试见
  :mod:`test_llm_router_tool_calls`
"""

import json

import requests
import pytest

from smart_assistant.tests.mock_llm_server import (
    TOOL_CALL_SCENARIOS,
    running_server,
)


# 标准 OpenAI tool schema fixture:覆盖 schedule/personnel/rag/memo/news 5 个工具
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
    },
    {
        "type": "function",
        "function": {
            "name": "personnel_query",
            "description": "查询人员",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_query",
            "description": "知识库问答",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memo_query",
            "description": "备忘录查询",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "news_query",
            "description": "新闻查询",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
]


@pytest.fixture
def mock_url():
    """进程内确定性 mock LLM 服务(端口 0 自动分配)。"""
    with running_server() as service:
        yield service.url


@pytest.fixture
def chat_url(mock_url):
    """拼接 /v1/chat/completions 路径,场景测试统一使用。"""
    return f"{mock_url}/v1/chat/completions"


def _post_chat(url, query, *, tools=None, tool_choice="auto"):
    """构造标准 chat.completion 请求 + POST + 返回解析 JSON。"""
    payload = {
        "model": "test",
        "messages": [{"role": "user", "content": query}],
    }
    if tools is not None:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
    r = requests.post(url, json=payload, timeout=5)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Step 2 测试:验证 Step 3 实现前为 FAIL
# ---------------------------------------------------------------------------


class TestToolCallScenarios:
    """验证 mock server 按 query 关键字返回预设 tool_calls 响应。"""

    def test_tomorrow_schedule_returns_tool_calls(self, chat_url):
        """'明天排班' + tools -> 返回 schedule_query 的 tool_calls。"""
        data = _post_chat(chat_url, "明天排班", tools=SAMPLE_TOOLS)

        assert data["choices"][0]["finish_reason"] == "tool_calls"
        tool_calls = data["choices"][0]["message"]["tool_calls"]
        assert len(tool_calls) == 1
        tc = tool_calls[0]
        assert tc["function"]["name"] == "schedule_query"
        # arguments 应是合法 JSON 字符串
        args = json.loads(tc["function"]["arguments"])
        assert "query" in args

    def test_personnel_query_returns_personnel_tool_call(self, chat_url):
        """'张三 在哪个部门' + tools -> 返回 personnel_query 的 tool_calls。"""
        data = _post_chat(chat_url, "张三在哪个部门", tools=SAMPLE_TOOLS)

        assert data["choices"][0]["finish_reason"] == "tool_calls"
        tc = data["choices"][0]["message"]["tool_calls"][0]
        assert tc["function"]["name"] == "personnel_query"
        args = json.loads(tc["function"]["arguments"])
        assert "name" in args

    def test_rag_query_returns_rag_tool_call(self, chat_url):
        """'报销制度' + tools -> 返回 rag_query tool_calls。"""
        data = _post_chat(chat_url, "公司报销制度是怎样的", tools=SAMPLE_TOOLS)

        assert data["choices"][0]["finish_reason"] == "tool_calls"
        tc = data["choices"][0]["message"]["tool_calls"][0]
        assert tc["function"]["name"] == "rag_query"

    def test_memo_query_returns_memo_tool_call(self, chat_url):
        """'备忘录' + tools -> 返回 memo_query tool_calls。"""
        data = _post_chat(chat_url, "查找上周备忘录", tools=SAMPLE_TOOLS)

        assert data["choices"][0]["finish_reason"] == "tool_calls"
        tc = data["choices"][0]["message"]["tool_calls"][0]
        assert tc["function"]["name"] == "memo_query"

    def test_news_query_returns_news_tool_call(self, chat_url):
        """'新闻' + tools -> 返回 news_query tool_calls。"""
        data = _post_chat(chat_url, "今天有什么新闻", tools=SAMPLE_TOOLS)

        assert data["choices"][0]["finish_reason"] == "tool_calls"
        tc = data["choices"][0]["message"]["tool_calls"][0]
        assert tc["function"]["name"] == "news_query"

    def test_no_tools_falls_through_to_default_answer(self, chat_url):
        """未带 tools 参数时,即使 query 含触发关键字,也走默认 FIXED_ANSWER(向后兼容)。"""
        from smart_assistant.tests.mock_llm_server import FIXED_ANSWER

        data = _post_chat(chat_url, "明天排班")  # 不带 tools
        assert data["choices"][0]["finish_reason"] == "stop"
        assert data["choices"][0]["message"]["content"] == FIXED_ANSWER

    def test_unknown_keyword_with_tools_returns_default_answer(self, chat_url):
        """带 tools 但 query 不在 TOOL_CALL_SCENARIOS 中 -> 走默认文本路径。"""
        from smart_assistant.tests.mock_llm_server import FIXED_ANSWER

        data = _post_chat(chat_url, "随便聊聊", tools=SAMPLE_TOOLS)
        assert data["choices"][0]["finish_reason"] == "stop"
        assert data["choices"][0]["message"]["content"] == FIXED_ANSWER

    def test_tool_call_payload_shape_matches_openai_spec(self, chat_url):
        """返回的 tool_calls 必须符合 OpenAI spec:[{id, type, function: {name, arguments}}]。"""
        data = _post_chat(chat_url, "明天排班", tools=SAMPLE_TOOLS)
        tc = data["choices"][0]["message"]["tool_calls"][0]

        # OpenAI spec 必须字段: id / type / function.{name, arguments}
        assert isinstance(tc["id"], str) and tc["id"].startswith("call_")
        assert tc["type"] == "function"
        assert "name" in tc["function"]
        assert "arguments" in tc["function"]
        # arguments 必须是 JSON 字符串(OpenAI 规范)
        json.loads(tc["function"]["arguments"])  # 可解析即为合法


class TestToolCallScenariosRegistry:
    """验证 TOOL_CALL_SCENARIOS 字典本体与覆盖域。"""

    def test_scenarios_cover_at_least_five_tools(self):
        """必须覆盖至少 5 个工具(schedule / personnel / rag / memo / news)。"""
        assert len(TOOL_CALL_SCENARIOS) >= 5, (
            f"TOOL_CALL_SCENARIOS 必须至少覆盖 5 个工具,实际 {len(TOOL_CALL_SCENARIOS)} 个"
        )

    def test_each_scenario_has_at_least_one_response(self):
        """每个场景至少 1 段预设响应(tool_calls 优先,后续可选 stop)。"""
        for kw, scenario in TOOL_CALL_SCENARIOS.items():
            assert isinstance(scenario, list) and len(scenario) >= 1, kw
            # 第一段响应通常应是 tool_calls(否则失去场景意义)
            first = scenario[0]
            choices = first["choices"]
            assert len(choices) >= 1, kw
            msg = choices[0]["message"]
            assert msg.get("tool_calls"), kw
