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

import pytest
from rest_framework.test import APIClient


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