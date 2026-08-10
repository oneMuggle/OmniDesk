"""P1A-2: 视图层透传 rate_limit_exceeded error_code + retry_after。

聚焦"视图层透传契约":验证 ``RateLimitHook`` 拒绝后,Orchestrator 透传
``error_code`` + ``retry_after`` 字段,视图层 create() 把它写入 JSON 响应。

适配说明(相对 brief verbatim):
- brief 写 ``monkeypatch.setattr(AgentOrchestrator, "process_query", ...)``,
  但 AgentOrchestrator 上不存在 ``process_query`` 方法(主入口是 ``process``),
  brief 自身 bug;此处改 patch ``process``(项目所有测试都用此模式)。
- brief 用 ``RequestFactory`` + 直接 ``req.user = user`` 试图绕过 DRF auth;
  但 DRF ``initial()`` 会重新跑 ``perform_authentication()`` 把 user 覆盖成
  ``AnonymousUser()``,``IsAuthenticated`` permission 必拒。改用项目惯例
  ``APIClient.force_authenticate(user=user)``(test_views.py / test_view_confirm_replay.py
  同样写法)。
"""

from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIClient

from smart_assistant.agent.orchestrator import AgentOrchestrator
from smart_assistant.hooks.base import HookEvent, Reject, ToolHookBase, get_registry
from smart_assistant.tools.base import BaseTool
from smart_assistant.tools.tool_context import ToolContext


# ---------------------------------------------------------------------------
# P1A-2 enforcement: orchestrator 必须阻断被 RateLimitHook 拒绝的工具执行
# ---------------------------------------------------------------------------


class _WriteToolForRateLimitTest(BaseTool):
    """require_confirmation=True 的写工具(用于验证 RateLimitHook 拦截路径)。

    ``executed_count`` 是类级计数器;test_orchestrator_confirm 同样用类变量
    作 spy 状态,避免引入额外 fixture 状态机。
    """

    name = "write_tool_for_rate_limit"
    description = "限流测试用写工具"
    intent_type = "write_rate_limit_intent"
    risk_level = "write"
    require_confirmation = True
    executed_count = 0

    def execute(self, query=None, context=None, **kwargs):
        # 计数 + 返回合法字典(若 orchestrator 不阻断,这里会被调用)
        _WriteToolForRateLimitTest.executed_count += 1
        return {"found": True, "result": "really_written"}


class _RateLimitRejectHook(ToolHookBase):
    """测试用 pre-hook:无条件返回 Reject(rate_limit_exceeded, retry_after)。

    与生产 RateLimitHook 的区别:不读 cache,不读环境变量,稳定可触发。
    用 ``priority=30`` 比生产 RateLimitHook(25)高,确保在 hook 链中先执行,
    但 RateLimitHook 在测试中不注册,不影响本测试。
    """

    name = "rate_limit_reject_test_hook"

    async def pre_execute(self, tool, ctx, params):
        return Reject(
            reason="写工具调用过于频繁,请 30 秒后再试。当前每用户每分钟上限 1 次",
            error_code="rate_limit_exceeded",
            retry_after=30,
        )


@pytest.fixture
def rate_limit_user():
    """mock 认证用户(id=42)"""
    user = MagicMock()
    user.pk = 42
    user.id = 42
    user.is_authenticated = True
    user.is_staff = False
    return user


@pytest.fixture
def rate_limit_tool_context(rate_limit_user):
    """mock ToolContext(scope=self, user=rate_limit_user)"""
    ctx = MagicMock(spec=ToolContext)
    ctx.user = rate_limit_user
    ctx.scope = MagicMock()
    ctx.scope.value = "self"
    return ctx


@pytest.fixture(autouse=True)
def _clean_rate_limit_registry():
    """每个测试后清空全局注册表,避免污染其他测试"""
    get_registry(reset=True)
    yield
    get_registry(reset=True)
    _WriteToolForRateLimitTest.executed_count = 0


@pytest.mark.django_db
class TestChatViewRateLimitPassthrough:
    def setup_method(self):
        from django.core.cache import cache

        cache.clear()
        self.client = APIClient()

    def _post_as(self, user):
        """以 user 身份 POST /api/smart-assistant/chat/,返回 DRF Response。"""
        self.client.force_authenticate(user=user)
        return self.client.post(
            "/api/smart-assistant/chat/",
            data={"query": "swap"},
            format="json",
        )

    def test_rate_limit_error_in_response(self, monkeypatch):
        """orchestrator 返回 rate_limit_exceeded 时,响应含 error_code + retry_after。"""
        from django.contrib.auth import get_user_model

        from smart_assistant.agent import orchestrator as orch_mod

        User = get_user_model()
        user = User.objects.create_user(username="p1a2_tester", password="x")

        # 用 monkeypatch 让 orchestrator 直接返回 rate_limit_exceeded error
        def fake_process(*args, **kwargs):
            return {
                "answer": "写工具调用过于频繁,请 30 秒后再试",
                "intent": "swap_request",
                "tool_used": "swap_request_tool",
                "tool_result": None,
                "error": True,
                "error_code": "rate_limit_exceeded",
                "retry_after": 30,
            }

        monkeypatch.setattr(orch_mod.AgentOrchestrator, "process", fake_process)

        resp = self._post_as(user)
        data = resp.json()

        assert resp.status_code == 200
        assert data["error"] is True
        assert data["error_code"] == "rate_limit_exceeded"
        assert data["retry_after"] == 30


@pytest.mark.django_db
class TestOrchestratorEnforcement:
    """P1A-2 enforcement: orchestrator 收到 RateLimitHook Reject 后应阻断工具执行。

    覆盖范围(按 brief Step 3 三处):
      1. ``_legacy_process`` (process() JSON 路径)
      2. ``process_stream`` (SSE 流式路径)
      3. ``_execute_native_tool`` (原生 Function Calling 路径,仅 staff)

    spy 模式:patch ``smart_assistant.agent.orchestrator.execute_guarded`` 计数;
    若 enforcement 生效,被 RateLimitHook Reject 后 ``execute_guarded`` 不被调用。

    实现选择说明(相对 brief Step 1 verbatim):
    - brief 草稿的 SpyWriteTool 走真实 swap_request_tool + 环境变量;实测会
      触发 LLM 调用,不稳定;改为自定义 ``_WriteToolForRateLimitTest`` +
      自定义 ``_RateLimitRejectHook`` 直接注入 Reject,沿用
      ``test_orchestrator_confirm`` 既有 mock 模式。
    - brief 草稿未覆盖 process_stream / _execute_native_tool;按 brief Step 3
      实际需要,补 2 个测试方法。
    """

    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    def test_legacy_process_blocks_tool_when_rate_limited(
        self, mock_classify, mock_chain_plan, rate_limit_tool_context
    ):
        """_legacy_process 在 RateLimitHook Reject 后,execute_guarded 不被调用,
        返回 dict 含 error_code + retry_after + error=True。"""
        mock_classify.return_value = "write_rate_limit_intent"
        mock_chain_plan.return_value = []  # 单工具路径

        # 注册 RateLimitRejectHook,触发 Reject(rate_limit_exceeded)
        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, _RateLimitRejectHook(), priority=30)

        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_WriteToolForRateLimitTest(),
        ), patch(
            "smart_assistant.agent.orchestrator.execute_guarded"
        ) as mock_exec_guarded:
            result = AgentOrchestrator().process(
                "写一个换班申请", tool_context=rate_limit_tool_context
            )

        # 关键断言 1:RateLimitHook Reject 后 execute_guarded 完全未被调用
        # (无 dry_run、无 confirmed 调用,直接阻断)
        assert mock_exec_guarded.call_count == 0
        # 关键断言 2:工具实际未执行
        assert _WriteToolForRateLimitTest.executed_count == 0
        # 关键断言 3:返回 dict 含 error_code + retry_after
        assert result.get("error") is True
        assert result.get("error_code") == "rate_limit_exceeded"
        assert result.get("retry_after") == 30
        assert "过于频繁" in result.get("answer", "")
        assert result.get("tool_used") == "write_tool_for_rate_limit"
        # 关键断言 4:不是 confirmation_required 路径(不应有 awaiting_confirmation)
        assert result.get("awaiting_confirmation") is not True

    @patch("smart_assistant.agent.orchestrator.execute_guarded")
    @patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan")
    @patch("smart_assistant.agent.orchestrator.classify_intent")
    def test_process_stream_blocks_tool_when_rate_limited(
        self, mock_classify, mock_chain_plan, mock_exec_guarded, rate_limit_tool_context
    ):
        """process_stream 在 RateLimitHook Reject 后,yield done 事件(带
        error_code/retry_after)并立即 return,不 yield 后续 chunk 事件,
        execute_guarded 不被调用。"""
        mock_classify.return_value = "write_rate_limit_intent"
        mock_chain_plan.return_value = []  # 单工具路径

        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, _RateLimitRejectHook(), priority=30)

        with patch(
            "smart_assistant.agent.orchestrator.ToolRegistry.get_tool",
            return_value=_WriteToolForRateLimitTest(),
        ):
            events = list(
                AgentOrchestrator().process_stream(
                    "写一个换班申请", [], rate_limit_tool_context
                )
            )

        # 关键断言 1:RateLimitHook Reject 后 execute_guarded 完全未被调用
        assert mock_exec_guarded.call_count == 0
        # 关键断言 2:工具实际未执行
        assert _WriteToolForRateLimitTest.executed_count == 0
        # 关键断言 3:SSE 流中有 done 事件且带 error_code/retry_after
        import json

        data_blob = "\n".join(events)
        assert "done" in data_blob
        # 解析最后一条 done 事件(包含 error_code/retry_after)
        done_payload = None
        for event in events:
            try:
                payload = event.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
                obj = json.loads(payload)
                if obj.get("type") == "done":
                    done_payload = obj
            except (IndexError, json.JSONDecodeError, ValueError):
                continue
        assert done_payload is not None, f"未解析到 done 事件,events={events}"
        assert done_payload.get("error") is True
        assert done_payload.get("error_code") == "rate_limit_exceeded"
        assert done_payload.get("retry_after") == 30
        # 关键断言 4:不应有 chunk 事件(工具未执行,无 LLM 输出)
        assert "chunk" not in data_blob

    def test_execute_native_tool_blocks_when_rate_limited(self, rate_limit_tool_context):
        """_execute_native_tool 在 RateLimitHook Reject 后,返回 error dict
        且不调用 execute_guarded。"""
        registry = get_registry()
        registry.register(HookEvent.PRE_EXECUTE, _RateLimitRejectHook(), priority=30)

        tool = _WriteToolForRateLimitTest()
        validated = {"query": "写一个换班申请"}

        with patch(
            "smart_assistant.agent.orchestrator.execute_guarded"
        ) as mock_exec_guarded:
            result, confirmation, failure = AgentOrchestrator()._execute_native_tool(
                tool, validated, rate_limit_tool_context
            )

        # 关键断言 1:execute_guarded 未被调用
        assert mock_exec_guarded.call_count == 0
        # 关键断言 2:工具实际未执行
        assert _WriteToolForRateLimitTest.executed_count == 0
        # 关键断言 3:返回 dict 含 error_code + retry_after
        assert isinstance(result, dict)
        assert result.get("error") is True
        assert result.get("error_code") == "rate_limit_exceeded"
        assert result.get("retry_after") == 30
        # 关键断言 4:not confirmation 路径(confirmation 应为 None)
        assert confirmation is None
