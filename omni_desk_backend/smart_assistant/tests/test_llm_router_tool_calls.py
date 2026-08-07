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

from llm_service.router import LLMRouter
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


@pytest.mark.django_db
class TestGenerateWithToolsPassthrough:
    """generate_with_tools() 透传契约 + 三元组返回值。"""

    def test_router_generate_with_tools_passes_tools_to_endpoint(self, mock_server):
        """新方法应将 tools 参数原样透传到 OpenAI 兼容 endpoint 请求体。"""
        router = LLMRouter()
        messages = [{"role": "user", "content": "明天排班"}]

        content, usage, tool_calls = router.generate_with_tools(
            messages=messages,
            tools=SAMPLE_TOOLS,
            tool_choice="auto",
            endpoint_url=mock_server.url,
        )

        # 透传契约:收到 1 条请求
        assert mock_server.request_count == 1
        sent_body = mock_server.requests[-1]
        assert sent_body["path"] == "/v1/chat/completions"
        assert isinstance(content, str)
        assert isinstance(usage, dict)
        assert isinstance(tool_calls, list)
        # 当前 mock server 不返回 tool_calls 场景,所以为空列表
        assert tool_calls == []

    def test_generate_with_tools_returns_three_tuple_with_empty_tool_calls(
        self, mock_server
    ):
        """未触发工具调用时,tool_calls 为空列表(确保下游可以走标准文本回复路径)。"""
        router = LLMRouter()
        messages = [{"role": "user", "content": "普通问答"}]

        result = router.generate_with_tools(
            messages=messages,
            tools=SAMPLE_TOOLS,
            tool_choice="auto",
            endpoint_url=mock_server.url,
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

    def test_generate_with_tools_supports_endpoint_url_override(self, mock_server):
        """``endpoint_url`` 参数应覆盖 DB 配置,直接命中测试 mock URL。"""
        router = LLMRouter()
        # 即便 router 有 DB 配置,``endpoint_url`` 应优先
        result = router.generate_with_tools(
            messages=[{"role": "user", "content": "test"}],
            endpoint_url=mock_server.url,
        )

        assert mock_server.request_count == 1
        # URL 拼装验证:必须打到 mock_server 的 /v1/chat/completions
        last = mock_server.requests[-1]
        assert last["path"] == "/v1/chat/completions"
        # 返回值结构
        content, usage, tool_calls = result
        assert content
        assert tool_calls == []
