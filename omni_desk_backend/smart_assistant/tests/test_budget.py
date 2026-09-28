"""AI 预算与配额（方案 5.6）：计量、上限解析、两级降级、接口。"""

import asyncio
import json
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from llm_service import metering
from llm_service.metering import (
    LlmBudgetExceeded,
    current_scope,
    estimate_tokens,
    iterate_in_scope,
    make_scope,
    record_call,
    usage_scope,
)
from llm_service.router import LLMRouter
from smart_assistant.budget.policy import budget_state, user_limits
from smart_assistant.budget.usage import today
from smart_assistant.hooks.builtin.budget import BudgetHook
from smart_assistant.hooks.base import Reject
from smart_assistant.models import (
    AgentLog,
    AgentTask,
    LlmAppConfig,
    LlmBudgetPolicy,
    LlmEndpoint,
    LlmUsageDaily,
)
from smart_assistant.tools.tool_context import ToolContext
from users.models import CustomUser

pytestmark = pytest.mark.django_db

CHAT_URL = "/api/smart-assistant/chat/"
STREAM_URL = "/api/smart-assistant/chat/stream/"


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, payload=None, lines=None):
        self._payload = payload
        self._lines = lines or []

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload

    def iter_lines(self):
        yield from self._lines


def _completion(content="好的", usage=None):
    payload = {"choices": [{"message": {"content": content}}]}
    if usage is not None:
        payload["usage"] = usage
    return payload


def _sse(obj):
    return f"data: {json.dumps(obj, ensure_ascii=False)}".encode()


@pytest.fixture
def fake_llm(monkeypatch):
    """替换路由的 HTTP 出口:记录请求体,按队列返回响应(默认带 usage 的固定回答)。"""
    import llm_service.router as router_mod

    state = SimpleNamespace(bodies=[], responses=[], error=None)

    def fake(method, url, **kwargs):
        state.bodies.append(kwargs.get("json"))
        if state.error is not None:
            raise state.error
        if state.responses:
            return state.responses.pop(0)
        return FakeResponse(_completion(usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}))

    monkeypatch.setattr(router_mod, "safe_internal_request", fake)
    monkeypatch.setattr(router_mod, "safe_request", fake)
    return state


def _user(username="alice", groups=()):
    user = CustomUser.objects.create_user(username=username, password="x")
    for name in groups:
        group, _ = Group.objects.get_or_create(name=name)
        user.groups.add(group)
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _default_policy(**fields):
    policy = LlmBudgetPolicy.objects.get(scope="default")
    for key, value in fields.items():
        setattr(policy, key, value)
    policy.save()
    return policy


def _usage(user=None, app="smart_assistant", staff="", calls=0, tokens=0, date=None):
    return LlmUsageDaily.objects.create(
        date=date or today(),
        user=user,
        user_key=user.pk if user else 0,
        app_name=app,
        staff_key=staff,
        calls=calls,
        total_tokens=tokens,
    )


# ---------------------------------------------------------------------------
# 计量
# ---------------------------------------------------------------------------


def test_default_policy_seeded_as_monitor_only():
    policy = LlmBudgetPolicy.objects.get(scope="default")
    assert (policy.daily_token_limit, policy.daily_call_limit, policy.soft_limit_percent) == (0, 0, 80)


def test_generate_records_usage_for_scope_user(fake_llm):
    user = _user()
    with usage_scope(user=user) as scope:
        content, _usage = LLMRouter("smart_assistant").generate("你好")
    assert content == "好的"
    row = LlmUsageDaily.objects.get()
    assert (row.user_id, row.app_name, row.calls, row.total_tokens, row.estimated_calls) == (
        user.pk,
        "smart_assistant",
        1,
        15,
        0,
    )
    assert scope.calls == 1 and scope.total_tokens == 15


def test_generate_without_usage_is_estimated(fake_llm):
    fake_llm.responses.append(FakeResponse(_completion("这是一个回答")))
    LLMRouter("office_assistant").generate("请帮我润色这段文字")
    row = LlmUsageDaily.objects.get(app_name="office_assistant")
    assert row.user_key == 0
    assert row.estimated_calls == 1
    assert row.total_tokens > 0


def test_estimate_tokens_counts_cjk_and_latin():
    assert estimate_tokens("") == 0
    assert estimate_tokens("你好世界") == 3  # 4 × 0.7 = 2.8 → 3
    assert estimate_tokens("abcdefgh") == 2


def test_failed_call_counts_failed(fake_llm):
    fake_llm.error = RuntimeError("down")
    with pytest.raises(RuntimeError):
        LLMRouter("smart_assistant").generate("你好")
    row = LlmUsageDaily.objects.get()
    assert (row.calls, row.failed_calls, row.total_tokens) == (0, 1, 0)


def test_metering_error_never_breaks_call(fake_llm, monkeypatch):
    def boom(**_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr("smart_assistant.budget.usage.add_usage", boom)
    content, _ = LLMRouter("smart_assistant").generate("你好")
    assert content == "好的"


def test_stream_records_usage_after_scope_exit(fake_llm):
    user = _user()
    fake_llm.responses.append(
        FakeResponse(
            lines=[
                _sse({"choices": [{"delta": {"content": "你"}}]}),
                _sse({"choices": [{"delta": {"content": "好"}}]}),
                _sse({"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9}}),
                b"data: [DONE]",
            ]
        )
    )
    with usage_scope(user=user):
        stream = LLMRouter("office_assistant").generate("hi", stream=True)
    # 流在 scope 之外被消费(StreamingHttpResponse 的真实情况),仍记在该用户名下
    assert "".join(stream) == "你好"
    row = LlmUsageDaily.objects.get()
    assert (row.user_id, row.total_tokens, row.estimated_calls) == (user.pk, 9, 0)


def test_stream_without_usage_is_estimated_and_counted_on_close(fake_llm):
    fake_llm.responses.append(
        FakeResponse(
            lines=[
                _sse({"choices": [{"delta": {"content": "第一段"}}]}),
                _sse({"choices": [{"delta": {"content": "第二段"}}]}),
            ]
        )
    )
    stream = LLMRouter("smart_assistant").generate("hi", stream=True)
    assert next(stream) == "第一段"
    stream.close()  # 客户端中途断开
    row = LlmUsageDaily.objects.get()
    assert row.calls == 1 and row.estimated_calls == 1 and row.total_tokens > 0


@pytest.mark.parametrize("caps,expected", [([{"stream_usage": True}], True), ([], False)])
def test_stream_options_only_when_endpoint_declares(fake_llm, caps, expected):
    endpoint = LlmEndpoint.objects.create(
        name="ep", api_endpoint="https://llm.example.com", api_key="k", is_active=True, model_capabilities=caps
    )
    LlmAppConfig.objects.create(app_name="smart_assistant", endpoint=endpoint, model_name="m", is_active=True)
    fake_llm.responses.append(FakeResponse(lines=[b"data: [DONE]"]))
    list(LLMRouter("smart_assistant").generate("hi", stream=True))
    assert ("stream_options" in fake_llm.bodies[0]) is expected


def test_generate_with_tools_records(fake_llm):
    user = _user()
    with usage_scope(user=user):
        LLMRouter("smart_assistant").generate_with_tools([{"role": "user", "content": "hi"}], tools=[])
    assert LlmUsageDaily.objects.get().total_tokens == 15


def test_staff_scope_is_not_user_usage():
    with usage_scope(staff_key="secretary"):
        record_call("smart_assistant", usage={"total_tokens": 40})
    row = LlmUsageDaily.objects.get()
    assert (row.user_key, row.staff_key, row.total_tokens) == (0, "secretary", 40)


def test_same_key_accumulates_single_row():
    user = _user()
    with usage_scope(user=user):
        record_call("smart_assistant", usage={"total_tokens": 10})
        record_call("smart_assistant", usage={"total_tokens": 5})
    row = LlmUsageDaily.objects.get()
    assert (row.calls, row.total_tokens) == (2, 15)


def test_ollama_client_records_native_counts(monkeypatch):
    import llm_service.ollama_client as mod

    monkeypatch.setattr(
        mod,
        "safe_internal_request",
        lambda *a, **k: FakeResponse({"message": {"content": "[]"}, "prompt_eval_count": 7, "eval_count": 3}),
    )
    user = _user()
    with usage_scope(user=user):
        assert mod.OllamaClient().generate("检查") == "[]"
    row = LlmUsageDaily.objects.get()
    assert (row.app_name, row.user_id, row.total_tokens, row.estimated_calls) == ("documents", user.pk, 10, 0)


def test_iterate_in_scope_enters_scope_on_every_step():
    scope = make_scope(staff_key="x")

    def gen():
        for _ in range(3):
            yield current_scope()

    seen = list(iterate_in_scope(gen(), scope))
    assert seen == [scope, scope, scope]
    assert current_scope() is None


def test_timeout_guard_thread_inherits_scope():
    from smart_assistant.hooks.builtin.timeout_guard import TimeoutGuardHook

    scope = make_scope(staff_key="t")
    with usage_scope(scope=scope):
        seen = TimeoutGuardHook(timeout=5, enabled=True).run_guarded_sync(current_scope)
    assert seen is scope


# ---------------------------------------------------------------------------
# 上限解析与状态
# ---------------------------------------------------------------------------


def test_user_limits_precedence():
    user = _user(groups=["研发", "测试"])
    _default_policy(daily_token_limit=1000)
    assert user_limits(user.pk).source == "全员默认"

    LlmBudgetPolicy.objects.create(scope="group", group=Group.objects.get(name="研发"), daily_token_limit=5000)
    LlmBudgetPolicy.objects.create(scope="group", group=Group.objects.get(name="测试"), daily_token_limit=3000)
    limits = user_limits(user.pk)
    assert limits.tokens == 5000  # 多个组取最宽松
    assert limits.source.startswith("用户组")

    LlmBudgetPolicy.objects.create(scope="group", group=Group.objects.create(name="VIP"), daily_token_limit=0)
    user.groups.add(Group.objects.get(name="VIP"))
    assert user_limits(user.pk).tokens == 0  # 0 = 不限,最宽松

    LlmBudgetPolicy.objects.create(scope="user", user=user, daily_token_limit=200)
    limits = user_limits(user.pk)
    assert (limits.tokens, limits.source) == (200, "个人")  # 个人覆盖优先


def test_states_readonly_and_blocked():
    user = _user()
    _default_policy(daily_call_limit=10)
    assert budget_state(user_id=user.pk).state == "ok"
    _usage(user, calls=8)
    state = budget_state(user_id=user.pk)
    assert state.state == "readonly" and "80%" in state.message
    LlmUsageDaily.objects.update(calls=10)
    state = budget_state(user_id=user.pk)
    assert state.blocked and "用完" in state.message


def test_yesterday_usage_does_not_count():
    user = _user()
    _default_policy(daily_call_limit=1)
    _usage(user, calls=5, date=today() - timedelta(days=1))
    assert budget_state(user_id=user.pk).state == "ok"


def test_app_limit_applies_to_everyone_and_includes_staff():
    user = _user()
    LlmBudgetPolicy.objects.create(scope="app", app_name="smart_assistant", daily_token_limit=100)
    _usage(None, staff="secretary", tokens=100)
    state = budget_state(user_id=user.pk)
    assert state.blocked
    assert "智能助手" in state.message
    # 数字员工的用量不算进个人
    assert state.user.usage["tokens"] == 0


def test_policy_change_takes_effect_immediately():
    user = _user()
    _usage(user, calls=5)
    assert budget_state(user_id=user.pk).state == "ok"
    _default_policy(daily_call_limit=5)  # 保存信号失效缓存
    assert budget_state(user_id=user.pk).blocked


# ---------------------------------------------------------------------------
# 硬上限:路由兜底 + 入口
# ---------------------------------------------------------------------------


def test_router_blocks_before_request(fake_llm):
    user = _user()
    _default_policy(daily_call_limit=1)
    _usage(user, calls=1)
    with usage_scope(user=user) as scope, pytest.raises(LlmBudgetExceeded):
        LLMRouter("smart_assistant").generate("hi")
    assert fake_llm.bodies == []
    assert "用完" in scope.blocked_message


def test_router_budget_check_error_fails_open(fake_llm, monkeypatch):
    def boom(**_kwargs):
        raise RuntimeError("cache down")

    monkeypatch.setattr("smart_assistant.budget.policy.blocked_message", boom)
    assert LLMRouter("smart_assistant").generate("hi")[0] == "好的"


@patch("smart_assistant.views.chat_sync.AgentOrchestrator")
def test_sync_chat_blocked_answers_without_orchestrator(orch_cls, admin_client, admin_user_obj):
    _default_policy(daily_call_limit=1)
    _usage(admin_user_obj, calls=1)
    resp = admin_client.post(CHAT_URL, {"query": "今天谁值班"}, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] is True
    assert data["kind"] == "budget_exceeded"
    assert data["error_code"] == "budget_exceeded"
    assert "用完" in data["answer"]
    assert data["budget"]["state"] == "blocked"
    orch_cls.assert_not_called()
    assert AgentLog.objects.filter(user_query="今天谁值班", tool_success=False).exists()


@patch("smart_assistant.views.chat_sync.AgentOrchestrator")
def test_sync_chat_readonly_disables_writes_and_task_cards(orch_cls, admin_client, admin_user_obj):
    _default_policy(daily_call_limit=10)
    _usage(admin_user_obj, calls=9)
    orch_cls.return_value.process.return_value = {"answer": "查询结果", "intent": "general_chat", "usage": None}
    resp = admin_client.post(CHAT_URL, {"query": "查一下"}, format="json")
    data = resp.json()
    assert data["error"] is False
    assert data["budget"]["state"] == "readonly"
    ctx = orch_cls.return_value.process.call_args.kwargs["tool_context"]
    assert ctx.budget_readonly is True
    assert ctx.task_proposal_allowed is False
    assert "90%" in ctx.budget_message


@patch("smart_assistant.views.chat_sync.AgentOrchestrator")
def test_sync_chat_ok_has_no_budget_field(orch_cls, admin_client):
    orch_cls.return_value.process.return_value = {"answer": "好", "intent": "general_chat", "usage": None}
    data = admin_client.post(CHAT_URL, {"query": "你好"}, format="json").json()
    assert data["budget"] is None
    ctx = orch_cls.return_value.process.call_args.kwargs["tool_context"]
    assert ctx.budget_readonly is False and ctx.task_proposal_allowed is True


@patch("smart_assistant.views.chat_sync.AgentOrchestrator")
def test_sync_chat_midturn_block_rewrites_failure(orch_cls, admin_client, admin_user_obj):
    _default_policy(daily_call_limit=2)
    _usage(admin_user_obj, calls=1)

    def process(query, history, tool_context=None):
        record_call("smart_assistant", usage={"total_tokens": 3})  # 本轮第一次调用把额度用满
        try:
            metering.check_before_call("smart_assistant")
        except LlmBudgetExceeded:
            return {"answer": "回答生成失败: LLM 不可用", "error": True, "intent": "general_chat"}
        return {"answer": "不应到这里"}

    orch_cls.return_value.process.side_effect = process
    data = admin_client.post(CHAT_URL, {"query": "写一份总结"}, format="json").json()
    assert data["kind"] == "budget_exceeded"
    assert "用完" in data["answer"]
    log = AgentLog.objects.get(user_query="写一份总结")
    assert log.total_tokens == 3  # 本轮计量合计回填


def _events(resp):
    raw = b"".join(resp.streaming_content).decode()
    return [json.loads(block[6:]) for block in raw.split("\n\n") if block.startswith("data: ")]


@patch("smart_assistant.views.chat_stream.AgentOrchestrator")
def test_stream_chat_blocked(orch_cls, admin_client, admin_user_obj):
    _default_policy(daily_token_limit=100)
    _usage(admin_user_obj, tokens=150)
    events = _events(admin_client.post(STREAM_URL, {"query": "你好"}, format="json"))
    orch_cls.assert_not_called()
    chunk = next(e for e in events if e["type"] == "chunk")
    done = next(e for e in events if e["type"] == "done")
    session = next(e for e in events if e["type"] == "session")
    assert "用完" in chunk["content"]
    assert done["kind"] == "budget_exceeded" and done["error"] is True
    assert session["kind"] == "budget_exceeded"
    assert session["budget"]["state"] == "blocked"


@patch("smart_assistant.views.chat_stream.AgentOrchestrator")
def test_stream_chat_logs_turn_usage(orch_cls, admin_client, admin_user_obj):
    def process_stream(query, conversation_history=None, tool_context=None):
        # LLM 调用发生在 StreamingHttpResponse 迭代时,应仍在该用户的计量范围内
        record_call("smart_assistant", usage={"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12})
        yield 'data: {"type": "chunk", "content": "流式回答"}\n\n'
        yield 'data: {"type": "done"}\n\n'

    orch_cls.return_value.process_stream.side_effect = process_stream
    events = _events(admin_client.post(STREAM_URL, {"query": "流式"}, format="json"))
    assert events[-1]["type"] == "session" and events[-1]["budget"] is None
    log = AgentLog.objects.get(user_query="流式")
    assert (log.input_tokens, log.output_tokens, log.total_tokens) == (8, 4, 12)
    assert LlmUsageDaily.objects.get().user_id == admin_user_obj.pk


# ---------------------------------------------------------------------------
# 只读:写工具 / 多步任务 / 办公助手
# ---------------------------------------------------------------------------


def _run_hook(tool, ctx):
    return asyncio.run(BudgetHook().pre_execute(tool, ctx, {"q": 1}))


def test_budget_hook_rejects_write_tools_only_when_readonly():
    write = SimpleNamespace(name="memo_create", require_confirmation=True)
    read = SimpleNamespace(name="memo_query", require_confirmation=False)
    readonly = ToolContext(user=None, budget_readonly=True, budget_message="额度已用 85%")

    result = _run_hook(write, readonly)
    assert isinstance(result, Reject)
    assert result.error_code == "budget_readonly"
    assert result.reason == "额度已用 85%"
    assert _run_hook(read, readonly) == {"q": 1}
    assert _run_hook(write, ToolContext(user=None)) == {"q": 1}
    assert _run_hook(write, {"budget_readonly": True, "replay": True}) == {"q": 1}


def test_budget_hook_registered_first():
    from smart_assistant.hooks.base import HookEvent, HookRegistry
    from smart_assistant.hooks.wiring import register_builtin_hooks

    reg = register_builtin_hooks(HookRegistry())
    names = [getattr(h, "name", None) for h in reg.list_hooks(HookEvent.PRE_EXECUTE)]
    assert names[0] == "budget_readonly"


def test_create_task_refused_when_readonly(admin_client, admin_user_obj):
    _default_policy(daily_call_limit=10)
    _usage(admin_user_obj, calls=8)
    resp = admin_client.post("/api/smart-assistant/tasks/create/", {"query": "安排下周试验并通知"}, format="json")
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "budget_readonly"
    assert not AgentTask.objects.exists()


def test_office_assistant_refused_when_readonly(admin_client, admin_user_obj, fake_llm):
    _default_policy(daily_call_limit=10)
    _usage(admin_user_obj, calls=8)
    resp = admin_client.post("/api/office_assistant/process/", {"action": "polish", "text": "你好"}, format="json")
    assert resp.status_code == 429
    assert resp.json()["error_code"] == "budget_readonly"
    assert fake_llm.bodies == []


def test_office_assistant_meters_user(admin_client, admin_user_obj, fake_llm):
    resp = admin_client.post("/api/office_assistant/process/", {"action": "polish", "text": "你好"}, format="json")
    assert resp.status_code == 200
    row = LlmUsageDaily.objects.get()
    assert (row.app_name, row.user_id) == ("office_assistant", admin_user_obj.pk)


def test_execute_agent_task_meters_task_owner():
    from smart_assistant.tasks import execute_agent_task

    user = _user()
    task = AgentTask.objects.create(task_id=uuid.uuid4(), user=user, objective="x", status="pending", task_packet={})

    def fake_execute(self):
        record_call("smart_assistant", usage={"total_tokens": 20})
        return SimpleNamespace(status="success", claim_lost=False, resume_claim_id=None)

    with (
        patch("smart_assistant.agents.packet.TaskPacket.from_dict", return_value=MagicMock()),
        patch("smart_assistant.agents.executor.MultiAgentExecutor.__init__", return_value=None),
        patch("smart_assistant.agents.executor.MultiAgentExecutor.execute", fake_execute),
    ):
        try:
            execute_agent_task.run(str(task.task_id))
        except Exception:  # 结果持久化细节不在本测试范围
            pass
    row = LlmUsageDaily.objects.get()
    assert (row.user_id, row.total_tokens) == (user.pk, 20)


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------


def test_me_reports_usage_even_without_limits():
    user = _user()
    _usage(user, calls=3, tokens=300)
    data = _client(user).get("/api/smart-assistant/budget/me/").json()
    assert data["state"] == "ok"
    assert data["user"]["usage"] == {"tokens": 300, "calls": 3}
    assert data["user"]["limits"]["source"] == "全员默认"
    assert data["user"]["percent"] is None


def test_policies_admin_only():
    user = _user()
    assert _client(user).get("/api/smart-assistant/budget/policies/").status_code == 403
    assert _client(user).get("/api/smart-assistant/budget/usage/").status_code == 403


def test_policy_crud_and_validation(admin_client, admin_user_obj):
    url = "/api/smart-assistant/budget/policies/"
    target = _user("bob")
    group = Group.objects.create(name="财务")

    rows = admin_client.get(url).json()
    assert [r["scope"] for r in rows] == ["default"]
    default_id = rows[0]["id"]

    assert admin_client.post(url, {"scope": "default"}, format="json").status_code == 400
    resp = admin_client.post(url, {"scope": "user", "user": target.pk, "daily_token_limit": 5000}, format="json")
    assert resp.status_code == 201, resp.json()
    assert resp.json()["updated_by_name"] == admin_user_obj.username
    dup = admin_client.post(url, {"scope": "user", "user": target.pk}, format="json")
    assert dup.status_code == 400 and "已有上限配置" in json.dumps(dup.json(), ensure_ascii=False)

    assert admin_client.post(url, {"scope": "group"}, format="json").status_code == 400
    assert admin_client.post(url, {"scope": "group", "group": group.pk}, format="json").status_code == 201
    assert admin_client.post(url, {"scope": "app", "app_name": "nope"}, format="json").status_code == 400
    app = admin_client.post(
        url, {"scope": "app", "app_name": "office_assistant", "daily_call_limit": 50}, format="json"
    )
    assert app.json()["app_label"] == "办公助手"

    assert admin_client.patch(f"{url}{default_id}/", {"soft_limit_percent": 0}, format="json").status_code == 400
    assert admin_client.patch(f"{url}{default_id}/", {"scope": "user"}, format="json").status_code == 400
    ok = admin_client.patch(
        f"{url}{default_id}/", {"daily_token_limit": 100000, "soft_limit_percent": 70}, format="json"
    )
    assert ok.status_code == 200
    assert admin_client.delete(f"{url}{default_id}/").status_code == 400
    assert admin_client.delete(f"{url}{app.json()['id']}/").status_code == 204


def test_usage_overview(admin_client, admin_user_obj):
    user = _user("carol")
    _default_policy(daily_token_limit=1000)
    _usage(user, tokens=900, calls=9)
    _usage(admin_user_obj, app="office_assistant", tokens=100, calls=1)
    _usage(None, staff="secretary", tokens=50, calls=2)
    _usage(user, tokens=10, calls=1, date=today() - timedelta(days=2))

    data = admin_client.get("/api/smart-assistant/budget/usage/?days=3").json()
    assert data["totals"]["tokens"] == 1050
    assert len(data["daily"]) == 3 and data["daily"][0]["tokens"] == 10
    assert data["top_users"][0]["user_display"] == "carol"
    assert data["top_users"][0]["state"] == "readonly"
    assert data["staff"][0]["staff_key"] == "secretary"
    apps = {a["app_name"]: a for a in data["apps"]}
    assert apps["smart_assistant"]["tokens"] == 950
    assert data["has_limits"] is True
    assert admin_client.get("/api/smart-assistant/budget/usage/?days=999").json()["days"] == 31


def test_user_search(admin_client):
    _user("dave")
    data = admin_client.get("/api/smart-assistant/budget/users/?q=dav").json()
    assert [u["label"] for u in data] == ["dave"]
