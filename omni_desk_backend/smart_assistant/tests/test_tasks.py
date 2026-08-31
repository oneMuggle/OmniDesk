"""Tests for smart_assistant Celery tasks."""

from unittest.mock import patch, MagicMock
from uuid import uuid4

from django.test import TestCase, TransactionTestCase

from smart_assistant.tasks import _notify_agent_task_result, process_document_embedding
from smart_assistant.agents.dataclasses import TaskResult


class TestAgentTaskResultNotification(TransactionTestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from smart_assistant.models import AgentTask

        self.user = get_user_model().objects.create_user(username="task-notify-user")
        self.task = AgentTask.objects.create(
            task_id=uuid4(),
            user=self.user,
            objective="测试任务",
            status="paused",
            task_packet={},
        )

    @patch("smart_assistant.tasks.NotificationService.create")
    def test_notifies_after_terminal_status_with_safe_summary(self, create):
        _notify_agent_task_result(self.task, "failed")

        create.assert_called_once()
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["user"], self.user)
        self.assertEqual(kwargs["type"], "agent_task_result")
        self.assertEqual(kwargs["dedupe_key"], f"agent_task:{self.task.task_id}")
        self.assertIn("失败", kwargs["content"])
        self.assertNotIn("异常原文", kwargs["content"])

    def test_notifies_cancelled_once_when_worker_repeats(self):
        from notifications.models import Notification

        _notify_agent_task_result(self.task, "cancelled")
        _notify_agent_task_result(self.task, "cancelled")

        notifications = Notification.objects.filter(
            user=self.user,
            type="agent_task_result",
            dedupe_key=f"agent_task:{self.task.task_id}",
        )
        self.assertEqual(notifications.count(), 1)
        self.assertIn("取消", notifications.get().content)


    def test_confirm_replay_rate_limit_rejects_without_consuming_token(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import get_confirmation_draft, set_confirmation_draft
        from smart_assistant.hooks.base import HookEvent, Reject, ToolHookBase, get_registry
        from smart_assistant.views.tasks import AgentTaskViewSet
        from smart_assistant.tools.notify_tool import NotifyTool

        token = "task-confirm-rate-limit-token"
        set_confirmation_draft(token, {
            "tool_name": "agent_notify", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "draft": {"fields": {"operation_id": "op-rate"}},
        })
        registry = get_registry()
        class RateReject(ToolHookBase):
            name = "rate_limit"
            async def pre_execute(self, tool, ctx, params):
                return Reject("too many", error_code="rate_limit_exceeded", retry_after=9)
        registry.register(HookEvent.PRE_EXECUTE, RateReject(), priority=30)
        request = APIRequestFactory().post("/confirm/", {"confirm_token": token}, format="json")
        force_authenticate(request, user=self.user)
        try:
            with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=NotifyTool()):
                response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))
        finally:
            registry.clear()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["error_code"], "rate_limit_exceeded")
        self.assertIsNotNone(get_confirmation_draft(token))

    def test_confirm_replay_permission_rejection_keeps_token(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import get_confirmation_draft, set_confirmation_draft
        from smart_assistant.hooks.base import HookEvent, Reject, ToolHookBase, get_registry
        from smart_assistant.views.tasks import AgentTaskViewSet
        from smart_assistant.tools.notify_tool import NotifyTool

        token = "task-confirm-permission-token"
        set_confirmation_draft(token, {
            "tool_name": "agent_notify", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "draft": {"fields": {"operation_id": "op-permission"}},
        })
        registry = get_registry()

        class PermissionReject(ToolHookBase):
            name = "permission"

            async def pre_execute(self, tool, ctx, params):
                return Reject("forbidden", error_code="permission_denied")

        registry.register(HookEvent.PRE_EXECUTE, PermissionReject(), priority=30)
        request = APIRequestFactory().post("/confirm/", {"confirm_token": token}, format="json")
        force_authenticate(request, user=self.user)
        try:
            with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=NotifyTool()):
                response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))
        finally:
            registry.clear()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error_code"], "permission_denied")
        self.assertIsNotNone(get_confirmation_draft(token))

    def test_confirm_replay_runs_pre_hooks_before_consuming_token(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import get_confirmation_draft, set_confirmation_draft
        from smart_assistant.hooks.base import HookEvent, ToolHookBase, get_registry
        from smart_assistant.views.tasks import AgentTaskViewSet
        from smart_assistant.tools.notify_tool import NotifyTool

        token = "task-confirm-pre-hook-token"
        set_confirmation_draft(token, {
            "tool_name": "agent_notify", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "draft": {"fields": {"recipient_ids": [self.user.id], "title": "标题", "content": "正文", "scope": "self", "operation_id": "op-pre"}},
        })
        registry = get_registry()
        calls = []

        class AuditPreHook(ToolHookBase):
            name = "audit_pre"

            async def pre_execute(self, tool, ctx, params):
                calls.append(getattr(ctx, "confirmed", False))
                return params

        registry.register(HookEvent.PRE_EXECUTE, AuditPreHook(), priority=30)
        request = APIRequestFactory().post("/confirm/", {"confirm_token": token}, format="json")
        force_authenticate(request, user=self.user)
        try:
            with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=NotifyTool(resolver=lambda _name, _actor: [self.user])), patch("notifications.channels.resolve_channels", return_value=[]):
                response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))
        finally:
            registry.clear()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [False])
        self.assertIsNone(get_confirmation_draft(token))
        self.assertEqual(response.data["status"], "confirmed")

    def test_confirm_replay_uses_pre_hook_modified_fields(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import get_confirmation_draft, set_confirmation_draft
        from smart_assistant.hooks.base import HookEvent, ToolHookBase, get_registry
        from smart_assistant.views.tasks import AgentTaskViewSet

        token = "task-confirm-pre-modified-token"
        set_confirmation_draft(token, {
            "tool_name": "observable_tool", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "draft": {"fields": {"recipient_ids": [999], "title": "旧标题", "content": "旧正文", "scope": "self", "operation_id": "op-modified"}},
        })
        registry = get_registry()
        observed = {}

        class ObservableTool:
            name = "observable_tool"
            require_confirmation = True

            @classmethod
            def get_openai_tool_schema(cls):
                return {"function": {"parameters": {"properties": {
                    "recipient_ids": {}, "title": {}, "content": {}, "scope": {},
                }}}}

            def execute(self, query=None, context=None, params=None, **kwargs):
                observed["query"] = query
                observed["context"] = context
                observed["params"] = params
                return {"found": True}

        class ModifyPreHook(ToolHookBase):
            name = "normalize"

            async def pre_execute(self, tool, ctx, params):
                return {**params, "recipient_ids": [user_id], "title": "新标题", "content": "新正文", "scope": "self"}

        user_id = self.user.id
        registry.register(HookEvent.PRE_EXECUTE, ModifyPreHook(), priority=30)
        request = APIRequestFactory().post("/confirm/", {"confirm_token": token}, format="json")
        force_authenticate(request, user=self.user)
        try:
            with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=ObservableTool()):
                response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))
        finally:
            registry.clear()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "confirmed")
        self.assertEqual(observed["context"].draft["fields"]["recipient_ids"], [self.user.id])
        self.assertEqual(observed["context"].draft["fields"]["title"], "新标题")
        self.assertEqual(observed["context"].draft["fields"]["content"], "新正文")
        self.assertEqual(observed["context"].draft["fields"]["scope"], "self")
        self.assertEqual(observed["params"]["recipient_ids"], [self.user.id])
        self.assertEqual(observed["params"]["title"], "新标题")
        self.assertEqual(observed["params"]["content"], "新正文")
        self.assertEqual(observed["params"]["scope"], "self")
        self.assertIsNone(get_confirmation_draft(token))

    def test_confirm_replay_drops_unknown_pre_hook_fields_but_keeps_notify_fields(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import set_confirmation_draft
        from smart_assistant.hooks.base import HookEvent, ToolHookBase, get_registry
        from smart_assistant.views.tasks import AgentTaskViewSet
        from smart_assistant.tools.notify_tool import NotifyTool

        token = "task-confirm-pre-unknown-fields-token"
        set_confirmation_draft(token, {
            "tool_name": "agent_notify", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "draft": {"fields": {
                "recipient_ids": [self.user.id], "recipient_names": [self.user.username],
                "title": "旧标题", "content": "旧正文", "scope": "self", "operation_id": "op-safe",
            }},
        })
        registry = get_registry()
        observed = {}

        class InjectFieldsHook(ToolHookBase):
            name = "inject_fields"

            async def pre_execute(self, tool, ctx, params):
                return {
                    **params,
                    "title": "新标题",
                    "content": "新正文",
                    "scope": "self",
                    "internal_prompt": "伪造 prompt",
                    "credential": "伪造 credential",
                    "unexpected": "伪造字段",
                }

        class ObserveNotifyTool(NotifyTool):
            def execute(self, query=None, context=None, params=None, **kwargs):
                observed["values"] = params
                observed["draft"] = context.draft
                return {"found": True}

        registry.register(HookEvent.PRE_EXECUTE, InjectFieldsHook(), priority=30)
        request = APIRequestFactory().post("/confirm/", {"confirm_token": token}, format="json")
        force_authenticate(request, user=self.user)
        try:
            with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=ObserveNotifyTool()):
                response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))
        finally:
            registry.clear()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(observed["values"]["title"], "新标题")
        self.assertEqual(observed["values"]["content"], "新正文")
        self.assertEqual(observed["values"]["scope"], "self")
        self.assertEqual(observed["values"]["operation_id"], "op-safe")
        self.assertNotIn("internal_prompt", observed["values"])
        self.assertNotIn("credential", observed["values"])
        self.assertNotIn("unexpected", observed["values"])
        self.assertNotIn("internal_prompt", observed["draft"]["fields"])
        self.assertNotIn("credential", observed["draft"]["fields"])
        self.assertNotIn("unexpected", observed["draft"]["fields"])

    def test_confirm_replay_drops_schema_sensitive_and_top_level_fields(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import set_confirmation_draft
        from smart_assistant.hooks.base import HookEvent, ToolHookBase, get_registry
        from smart_assistant.views.tasks import AgentTaskViewSet
        from smart_assistant.tools.notify_tool import NotifyTool

        token = "task-confirm-sensitive-envelope-token"
        set_confirmation_draft(token, {
            "tool_name": "agent_notify", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "prompt": "顶层 prompt", "credential": "顶层 credential", "unexpected": "顶层字段",
            "draft": {"summary": "安全摘要", "internal_prompt": "草稿 prompt", "credential": "草稿 credential", "fields": {
                "recipient_ids": [self.user.id], "title": "标题", "content": "正文", "scope": "self", "operation_id": "op-sensitive",
            }},
        })
        registry = get_registry()
        observed = {}

        class InjectSensitiveHook(ToolHookBase):
            name = "inject_sensitive"

            async def pre_execute(self, tool, ctx, params):
                observed["pre_draft"] = ctx.draft
                return {**params, "prompt": "hook prompt", "credential": "hook credential", "token": "hook token"}

        class ObserveTool(NotifyTool):
            @classmethod
            def get_openai_tool_schema(cls):
                schema = super().get_openai_tool_schema()
                schema["function"]["parameters"]["properties"].update({
                    "prompt": {"type": "string"}, "credential": {"type": "string"}, "token": {"type": "string"},
                })
                return schema

            def execute(self, query=None, context=None, params=None, **kwargs):
                observed["draft"] = context.draft
                observed["params"] = params
                return {"found": True}

        registry.register(HookEvent.PRE_EXECUTE, InjectSensitiveHook(), priority=30)
        request = APIRequestFactory().post("/confirm/", {"confirm_token": token}, format="json")
        force_authenticate(request, user=self.user)
        try:
            with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=ObserveTool()):
                response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))
        finally:
            registry.clear()

        self.assertEqual(response.status_code, 200)
        for snapshot in (observed["pre_draft"], observed["draft"]):
            self.assertNotIn("prompt", snapshot)
            self.assertNotIn("credential", snapshot)
            self.assertNotIn("unexpected", snapshot)
            self.assertNotIn("internal_prompt", snapshot.get("fields", {}))
        for key in ("prompt", "credential", "token"):
            self.assertNotIn(key, observed["params"])

    def test_confirm_replay_invalid_hook_fields_do_not_consume_or_execute(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import get_confirmation_draft, set_confirmation_draft
        from smart_assistant.hooks.base import HookEvent, ToolHookBase, get_registry
        from smart_assistant.views.tasks import AgentTaskViewSet
        from smart_assistant.tools.notify_tool import NotifyTool

        token = "task-confirm-invalid-hook-fields-token"
        set_confirmation_draft(token, {
            "tool_name": "agent_notify", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "draft": {"fields": {
                "recipient_ids": [self.user.id], "title": "标题", "content": "正文", "scope": "self", "operation_id": "op-invalid",
            }},
        })
        registry = get_registry()
        executed = []

        class InvalidHook(ToolHookBase):
            name = "invalid_fields"

            async def pre_execute(self, tool, ctx, params):
                return {**params, "scope": "global", "recipient_ids": "not-a-list"}

        class ObserveTool(NotifyTool):
            def execute(self, query=None, context=None, params=None, **kwargs):
                executed.append(params)
                return {"found": True}

        registry.register(HookEvent.PRE_EXECUTE, InvalidHook(), priority=30)
        request = APIRequestFactory().post("/confirm/", {"confirm_token": token}, format="json")
        force_authenticate(request, user=self.user)
        try:
            with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=ObserveTool()):
                response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))
        finally:
            registry.clear()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(executed, [])
        self.assertIsNotNone(get_confirmation_draft(token))

        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import set_confirmation_draft
        from smart_assistant.models import AgentEvent
        from smart_assistant.views.tasks import AgentTaskViewSet
        token = "task-notify-confirm-token"
        set_confirmation_draft(token, {
            "tool_name": "agent_notify", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "draft": {"fields": {"recipient_ids": [self.user.id], "title": "标题", "content": "正文", "scope": "self", "operation_id": "op-confirm"}},
        })
        factory = APIRequestFactory()
        request = factory.post(f"/tasks/{self.task.task_id}/confirm/", {"confirm_token": token}, format="json")
        force_authenticate(request, user=self.user)
        with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=__import__("smart_assistant.tools.notify_tool", fromlist=["NotifyTool"]).NotifyTool(resolver=lambda _name, _actor: [self.user])), patch("notifications.channels.resolve_channels", return_value=[]):
            response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "confirmed")
        self.assertEqual(response.data["result"]["failed_count"], 1)

    def test_confirm_replay_rejects_running_and_completed_tasks(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import set_confirmation_draft
        from smart_assistant.views.tasks import AgentTaskViewSet

        token = "task-confirm-status-token"
        set_confirmation_draft(token, {
            "tool_name": "agent_notify", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "draft": {"fields": {"operation_id": "op-status"}},
        })
        factory = APIRequestFactory()
        request = factory.post("/confirm/", {"confirm_token": token}, format="json")
        force_authenticate(request, user=self.user)
        self.task.status = "running"
        self.task.save(update_fields=["status"])
        response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))
        self.assertEqual(response.status_code, 409)

    def test_safe_plan_summary_accepts_task_packet_object(self):
        from smart_assistant.agents.packet import AgentRole, ExecutionMode, SubTask, TaskPacket
        from smart_assistant.views.tasks import _safe_plan_summary

        packet = TaskPacket(
            task_id=str(uuid4()), objective="目标", execution_mode=ExecutionMode.PIPELINE,
            subtasks=[SubTask(id="s1", role=AgentRole.RESEARCHER, objective="子目标")],
        )
        summary = _safe_plan_summary(packet)
        self.assertEqual(summary["objective"], "目标")
        self.assertEqual(summary["execution_mode"], "pipeline")
        self.assertEqual(summary["subtasks"][0]["id"], "s1")

    def test_confirm_response_contract_keeps_task_paused_and_records_intervention(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import set_confirmation_draft
        from smart_assistant.models import AgentEvent
        from smart_assistant.views.tasks import AgentTaskViewSet
        from smart_assistant.tools.notify_tool import NotifyTool

        token = "task-confirm-contract-token"
        set_confirmation_draft(token, {
            "tool_name": "agent_notify", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "draft": {"fields": {"recipient_ids": [self.user.id], "title": "标题", "content": "正文", "scope": "self", "operation_id": "op-contract"}},
        })
        request = APIRequestFactory().post("/confirm/", {"confirm_token": token, "operation_id": "op-contract"}, format="json")
        force_authenticate(request, user=self.user)
        with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=NotifyTool(resolver=lambda _name, _actor: [self.user])), patch("notifications.channels.resolve_channels", return_value=[]):
            response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "confirmed")
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "paused")
        event = AgentEvent.objects.get(task=self.task, event_type="user.intervention")
        self.assertEqual(event.payload["operation_id"], "op-contract")
        self.assertEqual(event.payload["status"], "confirmed")

    def test_notify_audit_event_has_no_recipient_identity_across_public_outputs(self):
        import json
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.models import AgentEvent
        from smart_assistant.tools.notify_tool import NotifyTool
        from smart_assistant.tools.tool_context import ToolContext
        from smart_assistant.agents.dataclasses import PersistentEventBus
        from smart_assistant.views.tasks import AgentEventSerializer, AgentTaskViewSet, _safe_event_payload
        from notifications.channels.types import NotifyResult

        class SentChannel:
            name = "sent-channel"
            def send(self, **kwargs):
                return NotifyResult(success=True)

        class FailedChannel:
            name = "failed-channel"
            def send(self, **kwargs):
                return NotifyResult(success=False)

        bus = PersistentEventBus(agent_task_id=str(self.task.task_id))
        tool = NotifyTool(resolver=lambda _name, _actor: [self.user])
        with patch("notifications.channels.resolve_channels", return_value=[SentChannel(), FailedChannel()]):
            tool.execute(context=ToolContext(
                user=self.user,
                confirmed=True,
                event_bus=bus,
                task_id=self.task.task_id,
                draft={"fields": {
                    "recipient_ids": [self.user.id], "recipient_names": ["普通中文姓名"],
                    "title": "标题", "content": "正文", "scope": "self", "operation_id": "op-public",
                }, "_resolved_users": [self.user]},
            ))

        event = AgentEvent.objects.get(task=self.task, event_type="subtask.tool_result")
        raw = json.dumps(event.payload, ensure_ascii=False)
        self.assertNotIn("user_id", raw)
        self.assertNotIn("recipient_id", raw)
        self.assertNotIn("普通中文姓名", raw)
        self.assertNotIn(self.user.username, raw)
        self.assertEqual(_safe_event_payload(event), {
            "operation_id": "op-public", "phase": "notify", "operation": "agent_notify",
            "recipient_count": 1, "sent_count": 1, "failed_count": 1,
            "channels": ["sent-channel", "failed-channel"],
            "sent": [{"channel": "sent-channel"}],
            "failed": [{"channel": "failed-channel", "reason": "send_failed"}],
        })
        self.assertEqual(AgentEventSerializer(event).data["payload"], _safe_event_payload(event))

        factory = APIRequestFactory()
        request = factory.get(f"/tasks/{self.task.task_id}/timeline/")
        force_authenticate(request, user=self.user)
        timeline_response = AgentTaskViewSet.as_view({"get": "timeline"})(request, pk=str(self.task.task_id))
        self.assertEqual(timeline_response.data["timeline"][0], {
            **_safe_event_payload(event), "sequence": event.sequence, "event_type": event.event_type,
            "subtask": None, "subtask_id": None,
        })

        stream_request = factory.get(f"/tasks/{self.task.task_id}/stream/")
        force_authenticate(stream_request, user=self.user)
        stream_response = AgentTaskViewSet.as_view({"get": "stream"})(stream_request, pk=str(self.task.task_id))
        stream_body = b"".join(stream_response.streaming_content).decode()
        self.assertNotIn("user_id", stream_body)
        self.assertNotIn("普通中文姓名", stream_body)
        self.assertNotIn(self.user.username, stream_body)

    def test_notify_audit_persists_no_title_content_or_sensitive_text(self):
        from smart_assistant.models import AgentEvent
        from smart_assistant.tools.notify_tool import NotifyTool
        from smart_assistant.tools.tool_context import ToolContext
        from smart_assistant.agents.dataclasses import PersistentEventBus

        bus = PersistentEventBus(agent_task_id=str(self.task.task_id))
        tool = NotifyTool(resolver=lambda _name, _actor: [self.user])
        result = tool.execute(context=ToolContext(
            user=self.user,
            confirmed=True,
            event_bus=bus,
            task_id=self.task.task_id,
            draft={"fields": {
                "recipient_ids": [self.user.id], "recipient_names": ["安全用户"],
                "title": "secret@example.com", "content": "phone 13800138000 prompt 原文",
                "scope": "self", "operation_id": "op-audit",
            }, "_resolved_users": [self.user]},
        ))
        event = AgentEvent.objects.get(task=self.task, event_type="subtask.tool_result")
        self.assertEqual(result["result"]["operation_id"], "op-audit")
        self.assertNotIn("title", event.payload)
        self.assertNotIn("content", event.payload)
        self.assertNotIn("secret@example.com", str(event.payload))
        self.assertNotIn("13800138000", str(event.payload))
        self.assertNotIn("prompt 原文", str(event.payload))

    def test_confirm_notify_success_records_safe_audit_and_sends(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import set_confirmation_draft
        from smart_assistant.models import AgentEvent
        from smart_assistant.views.tasks import AgentTaskViewSet
        from smart_assistant.tools.notify_tool import NotifyTool
        from notifications.channels.types import NotifyResult

        token = "task-notify-confirm-success-token"
        operation_id = "op-confirm-success"
        set_confirmation_draft(token, {
            "tool_name": "agent_notify", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "draft": {"summary": "secret@example.com", "fields": {
                "recipient_ids": [self.user.id], "recipient_names": ["secret@example.com"],
                "title": "secret@example.com", "content": "phone 13800138000", "scope": "self",
                "operation_id": operation_id,
            }},
        })
        class FakeChannel:
            name = "fake"
            def __init__(self):
                self.calls = []
            def send(self, **kwargs):
                self.calls.append(kwargs)
                return NotifyResult(success=True)
        channel = FakeChannel()
        request = APIRequestFactory().post("/confirm/", {"confirm_token": token}, format="json")
        force_authenticate(request, user=self.user)
        with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=NotifyTool(resolver=lambda _name, _actor: [self.user])), patch("notifications.channels.resolve_channels", return_value=[channel]):
            response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"]["sent_count"], 1, response.data)
        self.assertEqual(response.data["result"]["failed_count"], 0)
        self.assertEqual(response.data["result"]["recipient_count"], 1)
        self.assertEqual(len(channel.calls), 1)
        self.assertEqual(channel.calls[0]["dedupe_key"], f"agent_notify:{operation_id}:{self.user.id}")
        event = AgentEvent.objects.get(task=self.task, event_type="subtask.tool_result")
        self.assertEqual(event.payload["phase"], "notify")
        self.assertEqual(event.payload["operation"], "agent_notify")
        self.assertEqual(event.payload["operation_id"], operation_id)
        self.assertEqual(event.payload["recipient_count"], 1)
        self.assertNotIn("secret@example.com", str(event.payload))
        self.assertNotIn("13800138000", str(event.payload))
        self.assertNotIn("title", event.payload)
        self.assertNotIn("content", event.payload)


    def test_notify_dry_run_summary_is_short_and_excludes_body_and_secret_title(self):
        from smart_assistant.tools.notify_tool import NotifyTool
        from smart_assistant.tools.tool_context import ToolContext

        tool = NotifyTool(resolver=lambda _name, _actor: [self.user])
        result = tool.execute(
            params={
                "recipients": [self.user.username],
                "title": "api_key=secret@example.com 标题",
                "content": "正文中的 credential=super-secret 不应进入摘要",
                "scope": "self",
            },
            context={"user": self.user, "dry_run": True},
        )
        summary = result["draft"]["summary"]
        assert "agent_notify" in summary
        assert "收件人数：1" in summary
        assert "正文中的" not in summary
        assert "super-secret" not in summary
        assert "secret@example.com" not in summary
        assert len(summary) < 180
        # server-side draft 保留 confirmed replay 所需字段；API 只暴露安全摘要。
        assert result["draft"]["fields"]["content"].startswith("正文中的")
        from smart_assistant.views.tasks import _safe_replay_draft
        public_draft = _safe_replay_draft(result["draft"], {"operation_id": result["draft"]["fields"]["operation_id"]})
        assert "content" not in public_draft["fields"]
        assert "super-secret" not in str(public_draft)

    def test_confirm_notify_without_channel_returns_safe_failure(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from smart_assistant.cache import set_confirmation_draft
        from smart_assistant.views.tasks import AgentTaskViewSet
        from smart_assistant.tools.notify_tool import NotifyTool

        token = "task-notify-no-channel-token"
        set_confirmation_draft(token, {
            "tool_name": "agent_notify", "user_query": "通知",
            "context_sig": f"u{self.user.pk}_sself", "task_id": str(self.task.task_id),
            "draft": {"fields": {"recipient_ids": [self.user.id], "title": "标题", "content": "正文", "scope": "self", "operation_id": "op-no-channel"}},
        })
        factory = APIRequestFactory()
        request = factory.post("/confirm/", {"confirm_token": token}, format="json")
        force_authenticate(request, user=self.user)
        with patch("smart_assistant.tools.registry.ToolRegistry.get_tool_for_user", return_value=NotifyTool(resolver=lambda _name, _actor: [self.user])), patch("notifications.channels.resolve_channels", return_value=[]):
            response = AgentTaskViewSet.as_view({"post": "confirm"})(request, pk=str(self.task.task_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "confirmed")
        self.assertEqual(response.data["result"]["failed_count"], 1)


    def test_calculate_time_limits_uses_task_budget_and_packet_shape(self):
        from django.test import override_settings
        from smart_assistant.tasks import calculate_agent_task_time_limits

        task = MagicMock(
            global_budget=20000,
            task_packet={
                "subtasks": [{}, {}],
                "final_synthesis": {"objective": "合成"},
                "timeout_seconds": 50,
            },
        )
        with override_settings(
            LLM_REQUEST_TIMEOUT_SECONDS=10,
            AGENT_TASK_RETRY_COEFFICIENT=2,
            AGENT_TASK_MAX_SECONDS=1000,
        ):
            soft, hard = calculate_agent_task_time_limits(task)

        assert soft == 50
        assert hard == 110

    def test_calculate_time_limits_respects_packet_timeout_and_maximum(self):
        from django.test import override_settings
        from smart_assistant.tasks import calculate_agent_task_time_limits

        task = MagicMock(
            global_budget=1000,
            task_packet={
                "subtasks": [{}, {}, {}],
                "timeout_seconds": 700,
            },
        )
        with override_settings(
            LLM_REQUEST_TIMEOUT_SECONDS=100,
            AGENT_TASK_RETRY_COEFFICIENT=2,
            AGENT_TASK_MAX_SECONDS=250,
        ):
            assert calculate_agent_task_time_limits(task) == (250, 310)

    @patch("smart_assistant.tasks.execute_agent_task")
    def test_dispatch_uses_apply_async_with_dynamic_limits(self, mock_task):
        from smart_assistant.tasks import dispatch_agent_task

        task = MagicMock(task_id="task-1", global_budget=1000, task_packet={"subtasks": [{}]})
        dispatch_agent_task(task)

        mock_task.apply_async.assert_called_once()
        assert mock_task.apply_async.call_args.kwargs["args"] == ["task-1"]
        kwargs = mock_task.apply_async.call_args.kwargs
        assert kwargs["time_limit"] > kwargs["soft_time_limit"]

    def test_missing_agent_task_does_not_raise_for_autoretry(self):
        from smart_assistant.models import AgentTask
        from smart_assistant.tasks import execute_agent_task

        with patch.object(AgentTask, "objects") as objects:
            objects.select_for_update.return_value.get.side_effect = AgentTask.DoesNotExist
            assert execute_agent_task.run("missing-task") is None


    def test_paused_task_failed_resume_does_not_emit_completed(self):
        from django.contrib.auth import get_user_model
        from smart_assistant.models import AgentEvent, AgentTask
        from smart_assistant.tasks import execute_agent_task

        task = AgentTask.objects.create(
            task_id=uuid4(), user=get_user_model().objects.create_user(username="resume-failed-worker"),
            objective="恢复失败", status="paused", task_packet={"execution_mode": "not-a-mode"},
        )
        with patch("llm_service.router.get_router"), patch("smart_assistant.tools.registry.ToolRegistry"):
            result = execute_agent_task.run(str(task.task_id))

        task.refresh_from_db()
        assert result["status"] == "failed"
        assert task.status == "failed"
        assert task.completed_at is not None
        events = AgentEvent.objects.filter(task=task)
        assert events.filter(event_type="task.failed").count() == 1
        assert not events.filter(event_type="task.completed").exists()

    @patch("smart_assistant.agents.executor.MultiAgentExecutor")
    def test_executor_failed_result_persists_failed_event_with_safe_payload(self, executor_cls):
        from django.contrib.auth import get_user_model
        from smart_assistant.models import AgentEvent, AgentTask
        from smart_assistant.tasks import execute_agent_task

        task = AgentTask.objects.create(
            task_id=uuid4(),
            user=get_user_model().objects.create_user(username="executor-failed-result"),
            objective="执行失败结果",
            task_packet={"objective": "执行失败结果", "execution_mode": "pipeline", "subtasks": [{"id": "step1", "role": "researcher", "objective": "失败"}]},
        )
        executor_cls.return_value.execute.return_value = TaskResult(
            task_id=str(task.task_id), status="failed", final_output={"raw": "partial output"},
            total_tokens_used=17, error_message="模型失败",
        )

        result = execute_agent_task.run(str(task.task_id))

        task.refresh_from_db()
        assert result["status"] == "failed"
        assert task.status == "failed"
        event = AgentEvent.objects.get(task=task, event_type="task.failed")
        assert event.payload["error"] == "模型失败"
        assert event.payload["final_output"] == {"raw": "partial output"}
        assert event.payload["total_tokens"] == 17
        assert "dropped_events" in event.payload
        assert not AgentEvent.objects.filter(task=task, event_type="task.completed").exists()

    @patch("smart_assistant.agents.executor.MultiAgentExecutor.resume_from_checkpoint")
    def test_stale_resume_result_cannot_overwrite_new_claim(self, resume_mock):
        from django.contrib.auth import get_user_model
        from smart_assistant.models import AgentEvent, AgentTask
        from smart_assistant.tasks import execute_agent_task

        task = AgentTask.objects.create(
            task_id=uuid4(), user=get_user_model().objects.create_user(username="stale-resume-worker"), objective="旧恢复 claim", status="paused",
            task_packet={"execution_mode": "pipeline", "subtasks": []},
        )
        def replace_claim(*args, **kwargs):
            current = AgentTask.objects.get(task_id=task.task_id)
            current.status = "running"
            current.resume_claim_id = uuid4()
            current.save(update_fields=["status", "resume_claim_id", "updated_at"])
            return TaskResult(task_id=str(task.task_id), status="failed", error_message="旧 worker 失败")
        resume_mock.side_effect = replace_claim

        result = execute_agent_task.run(str(task.task_id))
        task.refresh_from_db()
        assert result["status"] == "running"
        assert task.status == "running"
        assert task.completed_at is None
        assert task.final_output is None
        assert not AgentEvent.objects.filter(task=task, event_type__in=["task.failed", "task.completed"]).exists()

    @patch("smart_assistant.agents.executor.MultiAgentExecutor.resume_from_checkpoint")
    def test_paused_task_uses_checkpoint_resume(self, resume_mock):
        """暂停任务重新派发必须走 checkpoint 恢复，而非普通 execute。"""
        from django.contrib.auth import get_user_model
        from smart_assistant.models import AgentTask
        from smart_assistant.tasks import execute_agent_task

        task = AgentTask.objects.create(
            task_id=uuid4(),
            user=get_user_model().objects.create_user(username="resume-worker"),
            objective="恢复",
        )
        task.status = "paused"
        task.task_packet = {
            "objective": "恢复", "execution_mode": "pipeline", "subtasks": [{
                "id": "step1", "role": "researcher", "objective": "第一步",
            }],
        }
        task.save(update_fields=["status", "task_packet"])
        resume_mock.return_value = MagicMock(
            status="success", total_tokens_used=0, final_output=None, subtask_results=[]
        )
        with patch("llm_service.router.get_router"), patch("smart_assistant.tools.registry.ToolRegistry"):
            execute_agent_task.run(str(task.task_id))
        resume_mock.assert_called_once()

    def test_real_resume_claim_loss_preserves_new_worker_state(self):
        from django.contrib.auth import get_user_model
        from smart_assistant.models import AgentEvent, AgentTask
        from smart_assistant.agents.executor import MultiAgentExecutor
        from smart_assistant.agents.packet import ExecutionMode
        from smart_assistant.tasks import execute_agent_task

        task = AgentTask.objects.create(
            task_id=uuid4(),
            user=get_user_model().objects.create_user(username="real-resume-claim"),
            objective="真实恢复 claim",
            status="paused",
            task_packet={"objective": "真实恢复 claim", "execution_mode": ExecutionMode.PIPELINE.value, "subtasks": [{"id": "step1", "role": "researcher", "objective": "step"}]},
            final_output={"old": "output"},
        )
        from django.utils import timezone
        started_at = timezone.now()
        task.started_at = started_at
        task.save(update_fields=["started_at"])

        def stale_worker_result(self):
            current = AgentTask.objects.get(task_id=task.task_id)
            current.status = "running"
            current.resume_claim_id = uuid4()
            current.final_output = {"new": "worker"}
            current.save(update_fields=["status", "resume_claim_id", "final_output", "updated_at"])
            return TaskResult(task_id=str(task.task_id), status="failed", error_message="旧 worker 失败")

        with patch.object(MultiAgentExecutor, "_execute_resume", stale_worker_result):
            result = execute_agent_task.run(str(task.task_id))

        task.refresh_from_db()
        assert result["status"] == "running"
        assert task.status == "running"
        assert task.resume_claim_id is not None
        assert task.started_at == started_at
        assert task.completed_at is None
        assert task.final_output == {"new": "worker"}
        assert not AgentEvent.objects.filter(task=task, event_type__in=["task.failed", "task.completed"]).exists()

    def test_executor_exception_has_one_complete_failure_event(self):
        from django.contrib.auth import get_user_model
        from smart_assistant.models import AgentEvent, AgentTask
        from smart_assistant.tasks import execute_agent_task

        task = AgentTask.objects.create(
            task_id=uuid4(),
            user=get_user_model().objects.create_user(username="executor-exception"),
            objective="异常失败",
            task_packet={"objective": "异常失败", "execution_mode": "pipeline", "subtasks": [{"id": "step1", "role": "researcher", "objective": "step"}]},
        )
        with patch("smart_assistant.agents.executor.MultiAgentExecutor.execute", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                execute_agent_task.run(str(task.task_id))

        events = AgentEvent.objects.filter(task=task, event_type="task.failed")
        assert events.count() == 1
        payload = events.get().payload
        assert payload["error"] == "agent task execution failed"
        assert payload["reason"] == "agent task execution failed"
        assert payload["final_output"] is None
        assert payload["total_tokens"] == 0
        assert "dropped_events" in payload
        assert not AgentEvent.objects.filter(task=task, event_type="task.completed").exists()

class TestProcessDocumentEmbedding(TestCase):
    """process_document_embedding Celery 任务测试."""

    @patch('smart_assistant.tasks.RagflowClient')
    @patch('ragflow_service.models.RagflowConfig')
    @patch('smart_assistant.tasks.getattr')
    def test_successful_embedding_process(self, mock_getattr, mock_ragflow_config, mock_ragflow_client_class):
        """文档成功上传到 Ragflow 并完成解析."""
        mock_getattr.return_value = 'test-dataset-id'

        mock_config_obj = MagicMock()
        mock_config_obj.api_endpoint = 'http://ragflow:8000'
        mock_config_obj.api_key = 'test-api-key'
        mock_ragflow_config.objects.filter.return_value.first.return_value = mock_config_obj

        mock_client = MagicMock()
        # upload_document 返回的是 data dict(以列表形式处理)
        mock_client.upload_document.return_value = {'id': 'ragflow-doc-123'}
        mock_client.parse_documents.return_value = True
        mock_ragflow_client_class.return_value = mock_client

        from smart_assistant.models import KnowledgeBaseDocument
        with patch.object(KnowledgeBaseDocument, 'objects') as mock_objects:
            mock_doc = MagicMock()
            mock_objects.get.return_value = mock_doc
            mock_doc.file.open.return_value.__enter__.return_value.read.return_value = b'test content'

            process_document_embedding('doc-1')

        assert mock_doc.embedding_status == 'completed'
        assert mock_doc.ragflow_document_id == 'ragflow-doc-123'
        assert mock_client.upload_document.called
        assert mock_client.parse_documents.called

    @patch('smart_assistant.tasks.getattr')
    @patch('ragflow_service.models.RagflowConfig')
    def test_missing_dataset_id_raises_error(self, mock_ragflow_config, mock_getattr):
        """SMART_ASSISTANT_DATASET_ID 未配置时任务失败."""
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from smart_assistant.models import KnowledgeBaseDocument

        # Create a real document so the except block can update it
        f = SimpleUploadedFile('test.txt', b'content', content_type='text/plain')
        doc = KnowledgeBaseDocument.objects.create(title='test', file=f)

        # Mock RagflowConfig so we reach the dataset_id check
        mock_config_obj = MagicMock()
        mock_config_obj.api_endpoint = 'http://ragflow:8000'
        mock_config_obj.api_key = 'test-key'
        mock_ragflow_config.objects.filter.return_value.first.return_value = mock_config_obj

        mock_getattr.return_value = None

        with self.assertRaisesRegex(ValueError, 'SMART_ASSISTANT_DATASET_ID'):
            process_document_embedding(doc.id)

        doc.refresh_from_db()
        self.assertEqual(doc.embedding_status, 'failed')

    @patch('ragflow_service.models.RagflowConfig')
    def test_missing_ragflow_config_raises_error(self, mock_ragflow_config):
        """Ragflow 配置未激活时任务失败."""
        from smart_assistant.models import KnowledgeBaseDocument

        mock_ragflow_config.objects.filter.return_value.first.return_value = None

        with patch.object(KnowledgeBaseDocument, 'objects') as mock_objects:
            mock_doc = MagicMock()
            mock_objects.get.return_value = mock_doc

            with self.assertRaisesRegex(ValueError, 'Ragflow 配置未激活'):
                process_document_embedding('doc-1')

    def test_document_not_found_silently_passes(self):
        """文档不存在时静默通过."""
        from smart_assistant.models import KnowledgeBaseDocument

        with patch.object(KnowledgeBaseDocument, 'objects') as mock_objects:
            mock_objects.get.side_effect = KnowledgeBaseDocument.DoesNotExist
            process_document_embedding('nonexistent-id')

    @patch('smart_assistant.tasks.RagflowClient')
    @patch('ragflow_service.models.RagflowConfig')
    @patch('smart_assistant.tasks.getattr')
    def test_upload_failure_marks_as_failed(self, mock_getattr, mock_ragflow_config, mock_ragflow_client_class):
        """上传失败时文档状态标记为 failed."""
        mock_getattr.return_value = 'test-dataset-id'

        mock_config_obj = MagicMock()
        mock_config_obj.api_endpoint = 'http://ragflow:8000'
        mock_config_obj.api_key = 'test-api-key'
        mock_ragflow_config.objects.filter.return_value.first.return_value = mock_config_obj

        # 模拟 upload_document 返回空数据
        mock_client = MagicMock()
        mock_client.upload_document.return_value = {}  # 返回空,触发 ValueError
        mock_ragflow_client_class.return_value = mock_client

        from smart_assistant.models import KnowledgeBaseDocument
        with patch.object(KnowledgeBaseDocument, 'objects') as mock_objects:
            mock_doc = MagicMock()
            mock_objects.get.return_value = mock_doc
            mock_doc.file.open.return_value.__enter__.return_value.read.return_value = b'test content'

            try:
                process_document_embedding('doc-1')
            except ValueError:
                pass

        assert mock_doc.embedding_status == 'failed'
