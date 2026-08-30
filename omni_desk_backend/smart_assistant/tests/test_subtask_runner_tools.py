import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

from smart_assistant.agents.dataclasses import EventBus
from smart_assistant.agents.packet import SubTask
from smart_assistant.agents.roles import AgentRole
from smart_assistant.agents.shared_context import SharedContext
from smart_assistant.agents.subtask_runner import SubTaskRunner
from smart_assistant.tools.tool_context import ToolContext


class FakeTool:
    name = "lookup"
    intent_type = "lookup"
    required_auth = True

    @classmethod
    def get_openai_tool_schema(cls):
        return {
            "type": "function",
            "function": {
                "name": "lookup",
                "description": "lookup",
                "parameters": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
            },
        }

    @classmethod
    def validate_arguments(cls, args):
        if not isinstance(args, dict) or "q" not in args:
            raise ValueError("bad arguments")
        return args

    def execute_with_guard(self, query, context):
        assert isinstance(context, ToolContext)
        return {"answer": f"found:{query}"}

    def execute(self, query=None, context=None, params=None, **kwargs):
        query = query or json.dumps(params, ensure_ascii=False)
        return {"answer": f"found:{query}"}


class ConfirmationTool(FakeTool):
    name = "write"
    intent_type = "write"
    require_confirmation = True

    @classmethod
    def get_openai_tool_schema(cls):
        schema = super().get_openai_tool_schema()
        schema["function"]["name"] = "write"
        return schema


class ConfirmationRegistry:
    @classmethod
    def get_openai_tools(cls, user):
        return [ConfirmationTool.get_openai_tool_schema()]

    @classmethod
    def get_tool_for_user(cls, name, user):
        return ConfirmationTool() if name == "write" and user is not None else None


class FakeRegistry:
    @classmethod
    def get_openai_tools(cls, user):
        return [FakeTool.get_openai_tool_schema()]

    @classmethod
    def get_tool_for_user(cls, name, user):
        return FakeTool() if name == "lookup" and user is not None else None


class FakeRouter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, **kwargs):
        return "legacy answer", {"total_tokens": 2}

    def generate_with_tools(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def make_subtask():
    return SubTask(id="s1", role=AgentRole.RESEARCHER, objective="查找信息")


def test_confirmation_is_returned_without_reinjection_or_second_llm_call(monkeypatch):
    user = MagicMock(is_authenticated=True)
    router = FakeRouter([
        ("", {"total_tokens": 1}, [{"id": "c1", "function": {"name": "write", "arguments": '{"q":"x"}'}}]),
    ])
    confirmation = {"token": "token-1", "draft": {"summary": "待确认写入"}}
    monkeypatch.setattr(
        "smart_assistant.agents.subtask_runner.execute_native_tool",
        lambda tool, validated, context: ({"found": True, "draft": confirmation["draft"]}, confirmation, None),
    )

    result = SubTaskRunner(
        router, EventBus(), 1, tool_registry=ConfirmationRegistry, user=user
    ).run(make_subtask(), SharedContext("q"))

    assert result.status == "awaiting_confirmation"
    assert result.output["awaiting_confirmation"] is True
    assert result.output["confirmation_token"] == "token-1"
    assert len(router.calls) == 1


def test_tool_call_is_validated_executed_and_reinjected():
    user = MagicMock(is_authenticated=True)
    router = FakeRouter([
        ("", {"total_tokens": 3}, [{"id": "c1", "function": {"name": "lookup", "arguments": '{"q":"abc"}'}}]),
        ("最终答案", {"total_tokens": 4}, []),
    ])
    bus = EventBus()
    result = SubTaskRunner(router, bus, 1, tool_registry=FakeRegistry, user=user).run(make_subtask(), SharedContext("q"))
    assert result.status == "success", result
    assert result.output == "最终答案"
    assert len(router.calls) == 2
    assert router.calls[1]["messages"][-1]["role"] == "tool"
    events = bus.get_events()
    assert [e.event_type for e in events].count("subtask.tool_call") == 1
    assert [e.event_type for e in events].count("subtask.tool_result") == 1
    assert events[1].payload["tool"] == "lookup"


def test_unknown_tool_is_rejected_without_execution_and_result_is_safe():
    user = MagicMock(is_authenticated=True)
    router = FakeRouter([
        ("", {"total_tokens": 1}, [{"id": "c1", "function": {"name": "nope", "arguments": "{}"}}]),
        ("done", {"total_tokens": 1}, []),
    ])
    result = SubTaskRunner(router, EventBus(), 1, tool_registry=FakeRegistry, user=user).run(make_subtask(), SharedContext("q"))

    assert result.status == "success"
    tool_message = router.calls[1]["messages"][-1]
    assert json.loads(tool_message["content"]) == {"error": "tool_unavailable"}


def test_tool_round_limit_finishes_with_tool_choice_none():
    user = MagicMock(is_authenticated=True)
    call = {"id": "c1", "function": {"name": "lookup", "arguments": '{"q":"x"}'}}
    router = FakeRouter([
        ("", {"total_tokens": 1}, [call]),
        ("", {"total_tokens": 1}, [call]),
        ("forced final", {"total_tokens": 1}, []),
    ])
    runner = SubTaskRunner(router, EventBus(), 1, tool_registry=FakeRegistry, user=user, max_tool_call_rounds=2)
    result = runner.run(make_subtask(), SharedContext("q"))

    assert result.output == "forced final"
    assert router.calls[-1]["tool_choice"] == "none"
    assert router.calls[-1]["messages"][0]["role"] == "system"
    assert router.calls[-1]["options"]["max_tokens"] > 0
    assert len(router.calls) == 3


def test_tool_call_event_redacts_pii_and_credentials():
    user = MagicMock(is_authenticated=True)
    router = FakeRouter([
        ("", {"total_tokens": 1}, [{"id": "c1", "function": {"name": "lookup", "arguments": json.dumps({
            "q": "alice@example.com 13812345678 110101199001011234",
            "api_key": "credential-value",
        })}}]),
        ("done", {"total_tokens": 1}, []),
    ])
    bus = EventBus()
    SubTaskRunner(router, bus, 1, tool_registry=FakeRegistry, user=user).run(make_subtask(), SharedContext("q"))
    event = next(e for e in bus.get_events() if e.event_type == "subtask.tool_call")
    rendered = json.dumps(event.payload, ensure_ascii=False)
    assert "alice@example.com" not in rendered
    assert "13812345678" not in rendered
    assert "credential-value" not in rendered
    assert "[REDACTED]" in rendered


def test_notify_confirmed_tool_context_persists_sanitized_audit_event(db):
    from django.contrib.auth import get_user_model
    from smart_assistant.agents.dataclasses import PersistentEventBus
    from smart_assistant.models import AgentEvent, AgentTask
    from smart_assistant.tools.notify_tool import NotifyTool
    from smart_assistant.tools.tool_context import ToolContext

    user = get_user_model().objects.create_user(username="notify-audit-user", real_name="审计用户")
    task = AgentTask.objects.create(task_id=uuid4(), user=user, objective="通知审计")
    bus = PersistentEventBus(agent_task_id=str(task.task_id))
    context = ToolContext(
        user=user, task_id=task.task_id, event_bus=bus, confirmed=True,
        draft={"fields": {"recipient_ids": [user.id], "title": "标题", "content": "正文", "scope": "self", "operation_id": "op-1"}},
    )
    tool = NotifyTool(resolver=lambda _name, _actor: [user])
    values = {
        "recipients": [user.username], "title": "标题 alice@example.com",
        "content": "正文 13812345678", "scope": "self",
        "recipient_ids": [user.id], "operation_id": "op-1",
    }

    with patch("smart_assistant.tools.notify_tool.resolve_channels", return_value=[]):
        result = tool.execute(params=values, context=context)

    assert result["found"] is True, result
    event = AgentEvent.objects.get(task=task, event_type="subtask.tool_result")
    assert event.payload["phase"] == "notify"
    assert event.payload["operation"] == "agent_notify"
    assert event.payload["operation_id"] == "op-1"
    assert event.payload["recipients"][0]["name"] == "notify-audit-user"
    assert event.payload["sent_count"] == 1
    assert event.payload["failed_count"] == 0
    rendered = json.dumps(event.payload, ensure_ascii=False)
    assert "alice@example.com" not in rendered
    assert "13812345678" not in rendered
    assert "credentials" not in rendered


def test_safe_summary_redacts_key_variants_and_preserves_nested_structure():
    value = {
        "emailAddress": "alice@example.com",
        "phoneNumber": "13812345678",
        "apiKey": "api-secret",
        "accessToken": "access-secret",
        "authorizationHeader": "Bearer credential",
        "nested": [{"身份证号": "110101900101123", "keep": "value"}, {"email_address": "bob@example.com"}],
    }

    summary = SubTaskRunner._safe_summary(value)

    assert list(summary) == list(value)
    assert len(summary["nested"]) == 2
    assert list(summary["nested"][0]) == ["身份证号", "keep"]
    assert summary["nested"][0]["keep"] == "value"
    for key in ("emailAddress", "phoneNumber", "apiKey", "accessToken", "authorizationHeader"):
        assert summary[key] == "[REDACTED]"
    assert summary["nested"][0]["身份证号"] == "[REDACTED]"
    assert summary["nested"][1]["email_address"] == "[REDACTED]"
    rendered = json.dumps(summary, ensure_ascii=False)
    for secret in ("alice@example.com", "13812345678", "api-secret", "access-secret", "Bearer credential", "110101900101123", "bob@example.com"):
        assert secret not in rendered


def test_budget_exhaustion_does_not_report_success():
    user = MagicMock(is_authenticated=True)
    router = FakeRouter([
        ("", {"total_tokens": 5}, [{"id": "c1", "function": {"name": "lookup", "arguments": '{"q":"x"}'}}]),
    ])
    context = SharedContext("q", global_budget=1)
    result = SubTaskRunner(router, EventBus(), 1, tool_registry=FakeRegistry, user=user).run(make_subtask(), context)

    assert result.status == "failed"
    assert result.error_message == "token budget exhausted"


    router = FakeRouter([])
    result = SubTaskRunner(router, EventBus(), 1).run(make_subtask(), SharedContext("q"))
    assert result.output == "legacy answer"
