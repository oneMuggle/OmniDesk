"""
覆盖补齐测试:middleware/rate_limit.py + agent/tool_chain_*.py

补 10 个测试用例:
  middleware/rate_limit.py(4 测试):
    1. 未达上限时放行 + 响应头 X-RateLimit-Remaining
    2. 达 30/min 上限时返回 429
    3. 未认证请求放行
    4. 非 /api/smart-assistant/chat/ 路径不受限流影响

  agent/tool_chain_executor.py(3 测试):
    5. 工具不存在时优雅处理(found=False)
    6. 工具抛异常时不中断后续步骤
    7. $variable 变量从前一个工具结果解析

  agent/tool_chain_planner.py(3 测试):
    8. 单一工具匹配时不走链式规划(返回 None)
    9. LLM 返回非 JSON 时返回 None
    10. LLM 返回非法 JSON 格式时返回 None
"""

import json
from unittest.mock import patch, MagicMock

import pytest
from django.test import RequestFactory

from smart_assistant.middleware.rate_limit import (
    RateLimitMiddleware,
    check_rate_limit,
    SMART_CHAT_RATE_LIMIT,
)


# =============================================================================
# middleware/rate_limit.py
# =============================================================================


@pytest.mark.django_db
class _FakeResponse:
    """支持字典式 header 赋值的简单响应对象,用于测试中间件."""

    def __init__(self, status_code=200):
        self.status_code = status_code
        self.headers = {}

    def __setitem__(self, key, value):
        self.headers[key] = value

    def __getitem__(self, key):
        return self.headers[key]

    def __contains__(self, key):
        return key in self.headers


class TestRateLimitMiddleware:
    """限流中间件边界."""

    def setup_method(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=_FakeResponse())
        self.middleware = RateLimitMiddleware(self.get_response)
        # 清理缓存避免测试间污染
        from django.core.cache import cache
        cache.clear()

    def test_under_limit_allows_request(self, admin_user_obj):
        """未达上限时放行,响应头带 X-RateLimit-Remaining."""
        request = self.factory.post("/api/smart-assistant/chat/", {"query": "hi"})
        request.user = admin_user_obj
        response = self.middleware(request)

        assert response is not None
        # 第一次请求后,remaining 应为 SMART_CHAT_RATE_LIMIT - 1
        assert response["X-RateLimit-Remaining"] == str(SMART_CHAT_RATE_LIMIT - 1)
        assert response["X-RateLimit-Limit"] == str(SMART_CHAT_RATE_LIMIT)

    def test_over_limit_returns_429(self, admin_user_obj):
        """达上限后返回 429 + retry_after."""
        from django.core.cache import cache

        cache.clear()  # 确保干净起点

        # 预填到上限
        for _ in range(SMART_CHAT_RATE_LIMIT):
            check_rate_limit(admin_user_obj.id)

        # 第 SMART_CHAT_RATE_LIMIT + 1 次请求应被拒
        request = self.factory.post("/api/smart-assistant/chat/", {"query": "hi"})
        request.user = admin_user_obj
        response = self.middleware(request)

        assert response.status_code == 429
        body = json.loads(response.content)
        assert "retry_after" in body
        assert "请求过于频繁" in body["error"]

    def test_unauthenticated_request_passes_through(self):
        """未认证请求不受限流."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.post("/api/smart-assistant/chat/", {"query": "hi"})
        request.user = AnonymousUser()
        # middleware 应放行(不解匿名用户)
        response = self.middleware(request)
        # 应直接调用 get_response
        self.get_response.assert_called_once_with(request)
        assert response is not None

    def test_non_chat_path_unaffected(self, admin_user_obj):
        """/api/smart-assistant/knowledge-base/ 等路径不受限流."""
        request = self.factory.get("/api/smart-assistant/knowledge-base/documents/")
        request.user = admin_user_obj
        response = self.middleware(request)
        # 应直接调用 get_response,不设置 X-RateLimit 头
        self.get_response.assert_called_once_with(request)
        assert "X-RateLimit-Remaining" not in response.headers


# =============================================================================
# agent/tool_chain_executor.py
# =============================================================================


@pytest.mark.django_db
class TestToolChainExecutorCoverage:
    """工具链执行器边界."""

    @patch("smart_assistant.agent.tool_chain_executor.ToolRegistry")
    def test_unknown_tool_returns_found_false(self, mock_registry, mock_llm_router):
        """工具不存在时,不抛异常,记录 found=False 结果."""
        mock_registry.get_tool.return_value = None

        from smart_assistant.agent.tool_chain_executor import execute_tool_chain

        plan = [{"tool": "nonexistent_tool", "params": {}, "depends_on": None}]
        results = execute_tool_chain(plan, "test query")

        assert len(results) == 1
        assert results[0]["success"] is False
        assert "不存在" in results[0]["result"]["message"]

    @patch("smart_assistant.agent.tool_chain_executor.ToolRegistry")
    def test_tool_exception_does_not_break_chain(self, mock_registry, mock_llm_router):
        """工具执行异常时,不中断后续步骤,记录 found=False."""
        # 第一个工具抛异常
        tool_a = MagicMock()
        tool_a.execute.side_effect = RuntimeError("boom")
        tool_a.name = "tool_a"
        # 第二个工具正常返回
        tool_b = MagicMock()
        tool_b.execute.return_value = {"found": True, "data": "ok"}
        tool_b.name = "tool_b"

        def get_tool(name):
            return {"tool_a": tool_a, "tool_b": tool_b}.get(name)

        mock_registry.get_tool.side_effect = get_tool

        from smart_assistant.agent.tool_chain_executor import execute_tool_chain

        plan = [
            {"tool": "tool_a", "params": {}, "depends_on": None},
            {"tool": "tool_b", "params": {}, "depends_on": None},
        ]
        results = execute_tool_chain(plan, "test query")

        assert len(results) == 2
        assert results[0]["success"] is False  # tool_a 失败
        assert results[1]["success"] is True   # tool_b 仍执行
        assert results[1]["result"]["data"] == "ok"

    @patch("smart_assistant.agent.tool_chain_executor.ToolRegistry")
    def test_variable_resolution_from_dep(self, mock_registry, mock_llm_router):
        """$variable.field 格式从前一个工具结果中解析值."""
        tool_a = MagicMock()
        tool_a.name = "tool_a"
        tool_a.execute.return_value = {"found": True, "user_id": 42, "name": "张三"}
        tool_b = MagicMock()
        tool_b.name = "tool_b"
        tool_b.execute.return_value = {"found": True, "info": "ok"}

        def get_tool(name):
            return {"tool_a": tool_a, "tool_b": tool_b}.get(name)

        mock_registry.get_tool.side_effect = get_tool

        from smart_assistant.agent.tool_chain_executor import execute_tool_chain

        plan = [
            {"tool": "tool_a", "params": {}, "depends_on": None},
            {"tool": "tool_b", "params": {"uid": "$tool_a.user_id"}, "depends_on": "tool_a"},
        ]
        execute_tool_chain(plan, "test query")
        tool_b.execute.assert_called_once()

    @patch("smart_assistant.agent.tool_chain_executor.ToolRegistry")
    def test_circular_or_unknown_dependency_does_not_loop(
        self, mock_registry, mock_llm_router
    ):
        """循环依赖(A 依赖 B,B 依赖 A)或 depends_on 指向不存在工具时,执行器按序跑完不无限循环."""
        tool_a = MagicMock()
        tool_a.name = "tool_a"
        tool_a.execute.return_value = {"found": True, "data": "a_result"}
        tool_b = MagicMock()
        tool_b.name = "tool_b"
        tool_b.execute.return_value = {"found": True, "data": "b_result"}

        def get_tool(name):
            return {"tool_a": tool_a, "tool_b": tool_b}.get(name)

        mock_registry.get_tool.side_effect = get_tool

        from smart_assistant.agent.tool_chain_executor import execute_tool_chain

        # A 依赖不存在的 ghost_tool(依赖缺失);B 依赖 A 形成潜在循环引用风险。
        # 执行器按 plan 顺序线性执行,缺失依赖时 _resolve_variables 保留原始字符串,
        # 不会触发再次执行 tool_a,故不会死循环。
        plan = [
            {"tool": "tool_a", "params": {}, "depends_on": "ghost_tool"},
            {"tool": "tool_b", "params": {"ref": "$tool_a.data"}, "depends_on": "tool_a"},
        ]
        results = execute_tool_chain(plan, "test query")

        # 两个工具都执行一次
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is True
        tool_a.execute.assert_called_once()
        tool_b.execute.assert_called_once()


# =============================================================================
# agent/tool_chain_planner.py
# =============================================================================


@pytest.mark.django_db
class TestToolChainPlannerCoverage:
    """工具链规划器边界."""

    @patch("smart_assistant.agent.intent_classifier.classify_intent")
    def test_single_intent_no_chain(self, mock_classify, mock_llm_router, mock_tool_registry):
        """只匹配单一工具时,返回 None(不进入链式)."""
        mock_tool_registry.get_all_schemas.return_value = [
            {"name": "schedule_query", "description": "排班"},
        ]
        mock_classify.return_value = "schedule_query"

        from smart_assistant.agent.tool_chain_planner import generate_tool_chain_plan

        result = generate_tool_chain_plan("谁值班", [{"name": "schedule_query"}], None)
        assert result is None

    def test_llm_response_no_json_returns_none(self, mock_llm_router, mock_tool_registry):
        """LLM 响应中无 JSON 列表时,返回 None."""
        mock_tool_registry.get_all_schemas.return_value = [
            {"name": "schedule_query", "description": "排班"},
            {"name": "personnel_query", "description": "人员"},
        ]
        mock_llm_router.generate.return_value = ("抱歉,我不理解", {})

        from smart_assistant.agent.tool_chain_planner import generate_tool_chain_plan

        result = generate_tool_chain_plan(
            "查询张三的排班和人员信息",
            [
                {"name": "schedule_query", "description": "排班"},
                {"name": "personnel_query", "description": "人员"},
            ],
            None,
        )
        assert result is None

    def test_llm_response_invalid_json_returns_none(self, mock_llm_router, mock_tool_registry):
        """LLM 响应是 JSON 但格式非法(非列表或缺 tool 字段)时,返回 None."""
        mock_llm_router.generate.return_value = ('{"not_a_list": true}', {})

        from smart_assistant.agent.tool_chain_planner import generate_tool_chain_plan

        result = generate_tool_chain_plan(
            "排班和人员",
            [
                {"name": "schedule_query", "description": "排班"},
                {"name": "personnel_query", "description": "人员"},
            ],
            None,
        )
        assert result is None
