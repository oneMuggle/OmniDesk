import pytest
from unittest.mock import patch

from notifications.models import Notification, NotificationPreference
from notifications.channels import InAppChannel, NotifyResult, resolve_channel
from notifications.service import NotificationService
from smart_assistant.scope import SmartAssistantScope
from smart_assistant.tools.notify_tool import AgentNotifyTool

@pytest.mark.django_db
def test_in_app_channel_delegates_to_service(regular_user_obj):
    with patch.object(NotificationService, "create", return_value=object()) as create:
        result = InAppChannel().send(user=regular_user_obj, type="agent_notify", title="提醒", content="内容")
    assert isinstance(result, NotifyResult)
    assert result.success is True
    create.assert_called_once_with(user=regular_user_obj, type="agent_notify", title="提醒", content="内容", link="", priority=Notification.PRIORITY_NORMAL)

@pytest.mark.django_db
def test_channel_resolution_falls_back_to_in_app_for_empty_or_unknown_settings(regular_user_obj):
    for settings in ({}, {"email": {"agent_notify": True}}, {"sms": {"agent_notify": True}}):
        NotificationPreference.objects.update_or_create(user=regular_user_obj, defaults={"channel_settings": settings})
        assert isinstance(resolve_channel(regular_user_obj, "agent_notify"), InAppChannel)

def test_agent_notify_schema_is_exact_and_confirmation_required():
    tool = AgentNotifyTool()
    assert tool.risk_level == "write"
    assert tool.require_confirmation is True
    schema = tool.get_openai_tool_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "agent_notify"
    assert schema["function"]["parameters"]["required"] == ["recipients", "title", "content", "scope"]
    assert schema["function"]["parameters"]["additionalProperties"] is False
    assert schema["function"]["strict"] is True

def test_agent_notify_requires_explicit_two_phase():
    result = AgentNotifyTool().execute(params={}, context={})
    assert result["found"] is False
    assert "dry_run" in result["message"]

@pytest.mark.django_db
def test_agent_notify_rejects_zero_or_multiple_name_candidates(regular_user_obj, monkeypatch):
    tool = AgentNotifyTool()
    monkeypatch.setattr(tool, "resolver", lambda name, actor: [])
    result = tool.execute(params={"recipients": ["不存在"], "title": "t", "content": "c", "scope": "self"}, context={"dry_run": True, "user": regular_user_obj})
    assert result["found"] is False
    monkeypatch.setattr(tool, "resolver", lambda name, actor: [regular_user_obj, regular_user_obj])
    result = tool.execute(params={"recipients": ["重名"], "title": "t", "content": "c", "scope": "self"}, context={"dry_run": True, "user": regular_user_obj})
    assert result["found"] is False

@pytest.mark.django_db
def test_agent_notify_mixed_channels_emit_audit_and_counts(regular_user_obj, admin_user_obj, monkeypatch):
    tool = AgentNotifyTool(resolver=lambda name, actor: [regular_user_obj] if name == "a" else [admin_user_obj])
    class Channel:
        def __init__(self, name, success): self.name, self.success = name, success
        def send(self, **kwargs): return NotifyResult(self.success, "ok" if self.success else "failed")
    monkeypatch.setattr("notifications.channels.resolve_channels", lambda user, intent: [Channel("in_app", user == regular_user_obj), Channel("email", False)] if user == regular_user_obj else [Channel("in_app", False)])
    from smart_assistant.agents.dataclasses import EventBus
    bus = EventBus()
    draft = tool.execute(params={"recipients": ["a", "b"], "title": "联系 a@example.com", "content": "13812345678", "scope": "global"}, context={"dry_run": True, "user": admin_user_obj})
    result = tool.execute(params={}, context={"confirmed": True, "user": admin_user_obj, "draft": draft["draft"], "event_bus": bus})
    assert result["found"] is False
    payload = bus.get_events()[0].payload
    assert result["result"]["sent_count"] == len(payload["sent"])
    assert result["result"]["failed_count"] == len(payload["failed"])
    assert result["result"]["recipient_count"] == 2
    assert payload["operation_id"]
    assert "@example.com" not in payload["content"]
    assert "13812345678" not in payload["content"]


@pytest.mark.django_db
def test_agent_notify_dry_run_then_confirmed_sends(regular_user_obj, monkeypatch):
    tool = AgentNotifyTool()
    monkeypatch.setattr(tool, "resolver", lambda name, actor: [regular_user_obj])
    params = {"recipients": ["张三"], "title": "t", "content": "c", "scope": "self"}
    draft = tool.execute(params=params, context={"dry_run": True, "user": regular_user_obj})
    assert draft["found"] is True
    with patch.object(InAppChannel, "send", return_value=NotifyResult(True, "ok")) as send:
        result = tool.execute(params=params, context={"confirmed": True, "user": regular_user_obj, "scope": SmartAssistantScope.SELF, "draft": draft["draft"]["fields"]})
    assert result["found"] is True
    assert result["result"]["sent_count"] == 1
    assert result["result"]["failed_count"] == 0
    assert result["result"]["recipient_count"] == 1
    send.assert_called_once()

@pytest.mark.django_db
def test_agent_notify_rejects_scope_mismatch(regular_user_obj, monkeypatch):
    tool = AgentNotifyTool()
    monkeypatch.setattr(tool, "resolver", lambda name, actor: [regular_user_obj])
    result = tool.execute(params={"recipients": ["张三"], "title": "t", "content": "c", "scope": "global"}, context={"dry_run": True, "user": regular_user_obj, "scope": SmartAssistantScope.SELF})
    assert result["found"] is False
    assert "scope" in result["message"]


def test_agent_notify_ignores_forged_dict_scope(regular_user_obj, monkeypatch):
    tool = AgentNotifyTool(resolver=lambda name, actor: [regular_user_obj])
    result = tool.execute(
        params={"recipients": ["张三"], "title": "t", "content": "c", "scope": "global"},
        context={"dry_run": True, "user": regular_user_obj, "scope": "global"},
    )
    assert result["found"] is False
    assert "scope" in result["message"]


def test_agent_notify_rejects_missing_confirmed_fields(regular_user_obj):
    result = AgentNotifyTool().execute(
        params={}, context={"confirmed": True, "user": regular_user_obj, "draft": {"recipient_ids": [regular_user_obj.id], "scope": "self"}}
    )
    assert result["found"] is False
    assert "title" in result["message"]


@pytest.mark.django_db
def test_agent_notify_filters_recipients_by_scope(regular_user_obj, admin_user_obj, monkeypatch):
    tool = AgentNotifyTool(resolver=lambda name, actor: [admin_user_obj])
    result = tool.execute(
        params={"recipients": ["管理员"], "title": "t", "content": "c", "scope": "self"},
        context={"dry_run": True, "user": regular_user_obj},
    )
    assert result["found"] is False
    assert "范围" in result["message"] or "scope" in result["message"]

@pytest.mark.django_db
def test_agent_notify_draft_contains_safe_recipient_audit_fields(regular_user_obj, monkeypatch):
    tool = AgentNotifyTool(resolver=lambda name, actor: [regular_user_obj])
    result = tool.execute(params={"recipients": ["张三"], "title": "  标题  ", "content": "  正文  ", "scope": "self"}, context={"dry_run": True, "user": regular_user_obj})
    fields = result["draft"]["fields"]
    assert fields["recipient_ids"] == [regular_user_obj.id]
    assert fields["recipient_names"] == [regular_user_obj.username]
    assert fields["title"] == "标题"
    assert fields["content"] == "正文"
    assert "credential" not in str(fields).lower()
    assert "prompt" not in str(fields).lower()
