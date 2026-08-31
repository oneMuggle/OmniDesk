"""AgentTask API 视图集

提供多 Agent 协作任务的 REST API + SSE 实时进度:
- list / retrieve: 查询任务列表和详情
- create_from_query: 用户查询 → Supervisor 分解 → 创建 AgentTask
- execute: 开始执行任务(异步)
- intervene: 用户介入(暂停/恢复/取消)
- stream: SSE 实时进度推送
- timeline: 完整时间线(甘特图数据)
"""

import json
import time
import re
import uuid
import copy

from django.db import transaction
from django.http import StreamingHttpResponse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..agents.supervisor import Supervisor
from ..agent.sse_contract import sse_event
from ..models import AgentEvent, AgentSubTask, AgentTask
from ..agents.dataclasses import PersistentEventBus
from ..hooks.base import Reject
from ..hooks.wiring import apply_failure_hooks, apply_post_execute_hooks, apply_pre_execute_hooks, execute_guarded
from ..tools.tool_context import ToolContext
from ..scope import resolve_scope
from llm_service.router import get_router
from observability import get_logger
from ..cache import safe_public_value, sanitize_public_text, public_tool_calls_meta, public_tool_result

logger = get_logger(__name__, "smart_assistant")

SAFE_EVENT_PAYLOAD_KEYS = {
    "event_type", "sequence", "subtask_id", "status", "content", "tool", "result", "task_id",
    "error", "reason", "final_output", "total_tokens", "dropped_events", "round",
    # notify 审计摘要：仅保留计数、通道结果和操作阶段，不保留收件人身份。
    "operation_id", "phase", "operation", "sent", "failed", "sent_count",
    "failed_count", "recipient_count", "channel", "channels",
}
SENSITIVE_KEYS = {
    "args", "arguments", "credentials", "credential", "token", "password", "secret", "prompt",
    "internal_prompt", "api_key", "access_token", "authorization", "access_key", "private_key", "session",
    "email", "phone", "phone_number", "身份证", "身份证号", "id_card", "idcard",
}
SENSITIVE_CANONICAL_PATTERNS = tuple(
    re.compile(pattern) for pattern in (
        r"(?:^|prompt)(?:text|value)?$", r"credential(?:blob)?$", r"token(?:value)?$",
        r"bearertoken$", r"clientsecret$", r"apikey$", r"accesstoken$",
        r"authorizationheader$", r"sessionid$",
    )
)


def _canonical_field_name(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


SENSITIVE_CANONICAL_KEYS = {_canonical_field_name(key) for key in SENSITIVE_KEYS}


def _is_sensitive_field(value):
    canonical = _canonical_field_name(value)
    return canonical in SENSITIVE_CANONICAL_KEYS or any(
        pattern.search(canonical) for pattern in SENSITIVE_CANONICAL_PATTERNS
    )

# These fields are persisted by confirmation drafts but are not all part of the
# public tool-call schema (for example NotifyTool resolves recipient names into
# IDs before replay).  Everything else must come from the tool schema.
REPLAY_INTERNAL_FIELD_ALLOWLIST = {"operation_id", "recipient_ids", "recipient_names"}


def _replay_allowed_fields(tool):
    """Return non-sensitive fields a hook may modify during replay."""
    allowed = {
        key for key in REPLAY_INTERNAL_FIELD_ALLOWLIST
        if not _is_sensitive_field(key)
    }
    try:
        schema = tool.get_openai_tool_schema()
        properties = schema.get("function", {}).get("parameters", {}).get("properties", {})
        if isinstance(properties, dict):
            allowed.update(
                key for key in properties
                if isinstance(key, str) and not _is_sensitive_field(key)
            )
    except (AttributeError, TypeError, KeyError) as exc:
        logger.debug("replay tool schema unavailable; using base allowlist: %s", type(exc).__name__)
    return allowed


def _filter_replay_fields(fields, allowed):
    if not isinstance(fields, dict):
        return {}
    return {key: value for key, value in fields.items() if key in allowed}


def _safe_replay_draft(draft, fields):
    """Build the minimal draft envelope exposed to hooks and confirmed tools."""
    safe_draft = {"fields": fields}
    if isinstance(draft, dict) and isinstance(draft.get("summary"), str):
        safe_draft["summary"] = _sanitize_text(draft["summary"])
    return safe_draft


def _validate_replay_fields(tool, fields):
    """Validate hook output before consuming the single-use confirmation token."""
    if getattr(tool, "name", None) == "agent_notify":
        recipient_ids = fields.get("recipient_ids")
        if (
            not isinstance(recipient_ids, list)
            or not 1 <= len(recipient_ids) <= 10
            or len(set(recipient_ids)) != len(recipient_ids)
            or any(not isinstance(item, int) or isinstance(item, bool) for item in recipient_ids)
        ):
            return "确认收件人参数无效"
        if fields.get("scope") not in {"self", "department", "global"}:
            return "确认范围参数无效"
        for key, limit in (("title", 200), ("content", 10000)):
            value = fields.get(key)
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
                return "确认通知参数无效"
            if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
                return "确认通知参数无效"
        return None
    validator = getattr(tool, "validate_arguments", None)
    if not callable(validator):
        return None
    try:
        validator(fields)
    except Exception:
        return "确认参数校验失败"
    return None


# 公开输出统一复用 cache 中的 sanitizer，避免 REST/SSE/timeline 规则漂移。
_sanitize_text = sanitize_public_text


def _safe_event_payload(event):
    payload = getattr(event, "payload", None)
    payload = payload if isinstance(payload, dict) else {}
    public = safe_public_value({key: payload[key] for key in SAFE_EVENT_PAYLOAD_KEYS if key in payload})
    for key in ("sent", "failed"):
        entries = payload.get(key)
        if not isinstance(entries, list):
            continue
        public[key] = [
            {
                field: safe_public_value(entry[field])
                for field in ("channel", "reason", "status")
                if field in entry and isinstance(entry, dict)
            }
            for entry in entries[:20]
            if isinstance(entry, dict)
        ]
    return public


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


PUBLIC_VALUE_KEYS = {
    "title", "summary", "content", "answer", "status", "message", "error", "reason",
    "tool", "phase", "operation", "round", "count", "total", "items", "result",
    "recipient_count", "sent_count", "failed_count", "channel", "channels",
}


def _safe_plan_summary(task_packet):
    """只向创建响应暴露计划摘要，兼容 TaskPacket 与字典。"""
    if isinstance(task_packet, dict):
        packet = task_packet
    elif hasattr(task_packet, "to_dict"):
        packet = task_packet.to_dict()
    else:
        packet = {
            "objective": getattr(task_packet, "objective", None),
            "execution_mode": getattr(getattr(task_packet, "execution_mode", None), "value", getattr(task_packet, "execution_mode", None)),
            "subtasks": getattr(task_packet, "subtasks", []),
        }
    subtasks = packet.get("subtasks") if isinstance(packet, dict) else []
    summary = {
        "objective": _sanitize_text(str(packet.get("objective") or "")),
        "execution_mode": packet.get("execution_mode"),
        "subtask_count": len(subtasks) if isinstance(subtasks, list) else 0,
    }
    if isinstance(subtasks, list):
        summary["subtasks"] = []
        for item in subtasks[:20]:
            if isinstance(item, dict):
                item_id, role, objective = item.get("id"), item.get("role"), item.get("objective", "")
            else:
                item_id = getattr(item, "id", None)
                role = getattr(getattr(item, "role", None), "value", getattr(item, "role", None))
                objective = getattr(item, "objective", "")
            summary["subtasks"].append({
                "id": item_id,
                "role": role,
                "objective": _sanitize_text(str(objective or "")),
            })
    return summary


def _safe_public_value(value):
    return safe_public_value(value)


class AgentSubTaskSerializer(serializers.ModelSerializer):
    objective = serializers.SerializerMethodField()
    inputs = serializers.SerializerMethodField()
    output = serializers.SerializerMethodField()
    error_message = serializers.SerializerMethodField()

    def get_objective(self, obj):
        return _sanitize_text(obj.objective or "")

    def get_inputs(self, obj):
        return _safe_public_value(obj.inputs if isinstance(obj.inputs, dict) else {})

    def get_output(self, obj):
        return _safe_public_value(obj.output)

    def get_error_message(self, obj):
        return _sanitize_text(obj.error_message) if obj.error_message else None

    class Meta:
        model = AgentSubTask
        fields = [
            "subtask_id", "role", "objective", "status", "depends_on", "inputs", "output",
            "tokens_used", "started_at", "completed_at", "retry_count", "error_message",
        ]


class AgentEventSerializer(serializers.ModelSerializer):
    payload = serializers.SerializerMethodField()

    def get_payload(self, obj):
        return _safe_event_payload(obj)

    class Meta:
        model = AgentEvent
        fields = ["sequence", "event_type", "subtask", "payload", "created_at"]


class AgentTaskSerializer(serializers.ModelSerializer):
    objective = serializers.SerializerMethodField()
    subtasks = AgentSubTaskSerializer(many=True, read_only=True)
    final_output = serializers.SerializerMethodField()

    def get_objective(self, obj):
        return _sanitize_text(obj.objective or "")

    def get_final_output(self, obj):
        return _safe_public_value(obj.final_output)

    class Meta:
        model = AgentTask
        # task_packet intentionally never leaves the API; it contains raw LLM inputs.
        fields = [
            "task_id", "objective", "execution_mode", "status", "global_budget", "tokens_used",
            "started_at", "completed_at", "final_output", "created_at", "updated_at", "subtasks",
        ]


class CreateTaskRequestSerializer(serializers.Serializer):
    query = serializers.CharField(required=True)
    user_context = serializers.DictField(required=False, default=dict)


# ---------------------------------------------------------------------------
# ViewSet
# ---------------------------------------------------------------------------


class AgentTaskViewSet(viewsets.ViewSet):
    """多 Agent 任务管理"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        """GET /api/smart-assistant/tasks/"""
        tasks = AgentTask.objects.filter(user=request.user).order_by("-created_at").prefetch_related("subtasks")
        serializer = AgentTaskSerializer(tasks, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """GET /api/smart-assistant/tasks/{task_id}/"""
        try:
            task = AgentTask.objects.get(task_id=pk, user=request.user)
        except AgentTask.DoesNotExist:
            return Response({"error": "任务不存在"}, status=status.HTTP_404_NOT_FOUND)
        serializer = AgentTaskSerializer(task)
        return Response(serializer.data)

    @action(detail=False, methods=["POST"], url_path="create")
    def create_from_query(self, request):
        """POST /api/smart-assistant/tasks/create/

        用户查询 → Supervisor 分解 → 创建 AgentTask
        """
        serializer = CreateTaskRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        query = serializer.validated_data["query"]
        user_context = serializer.validated_data.get("user_context", {})

        try:
            # 调用 Supervisor 生成 TaskPacket
            supervisor = Supervisor(llm_router=get_router())
            task_packet = supervisor.generate_task_packet(query=query, user_context=user_context)

            # 创建 AgentTask 记录
            with transaction.atomic():
                task = AgentTask.objects.create(
                    task_id=uuid.UUID(task_packet.task_id),
                    user=request.user,
                    objective=task_packet.objective,
                    execution_mode=task_packet.execution_mode.value,
                    status="pending",
                    task_packet=task_packet.to_dict(),
                    global_budget=task_packet.global_budget,
                )

                # 创建 AgentSubTask 记录
                AgentSubTask.objects.bulk_create([
                    AgentSubTask(
                        task=task,
                        subtask_id=subtask.id,
                        role=subtask.role.value,
                        objective=subtask.objective,
                        status="pending",
                        depends_on=subtask.depends_on,
                        inputs=subtask.inputs,
                    )
                    for subtask in task_packet.subtasks
                ])

            return Response(
                {
                    "task_id": str(task.task_id),
                    "status": task.status,
                    "plan": _safe_plan_summary(task_packet),
                },
                status=status.HTTP_201_CREATED,
            )

        except ValueError:
            logger.warning("智能助手任务计划校验失败: user_id=%s", request.user.pk)
            return Response(
                {"error": "任务计划无效", "error_code": "invalid_task_plan"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("智能助手任务创建异常: user_id=%s", request.user.pk)
            return Response(
                {"error": "任务创建失败，请稍后重试", "error_code": "task_creation_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["POST"])
    def execute(self, request, pk=None):
        """POST /api/smart-assistant/tasks/{task_id}/execute/

        开始执行任务(异步)
        """
        try:
            task = AgentTask.objects.get(task_id=pk, user=request.user)
        except AgentTask.DoesNotExist:
            return Response({"error": "任务不存在"}, status=status.HTTP_404_NOT_FOUND)

        from ..tasks import dispatch_agent_task

        with transaction.atomic():
            task = AgentTask.objects.select_for_update().get(task_id=pk, user=request.user)
            if task.status != "pending":
                return Response(
                    {"error": f"任务状态为 {task.status},无法执行"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            transaction.on_commit(lambda: dispatch_agent_task(task))

        return Response({"status": "started", "task_id": str(task.task_id)})

    @action(detail=True, methods=["POST"], url_path="confirm")
    def confirm(self, request, pk=None):
        """在任务锁内原子校验并消费确认令牌，然后重放写工具。"""
        from ..cache import ConfirmationDraftConsumeError, consume_confirmation_draft, get_confirmation_draft
        from ..tools.registry import ToolRegistry

        token = request.data.get("confirm_token")
        if not isinstance(token, str) or not token:
            return Response({"error": "确认令牌无效"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                task = AgentTask.objects.select_for_update().get(task_id=pk, user=request.user)
                if task.status != "paused":
                    return Response(
                        {"error": f"任务状态为 {task.status},无法确认"},
                        status=status.HTTP_409_CONFLICT,
                    )
                entry = get_confirmation_draft(token)
                expected_sig = f"u{request.user.pk}_s{resolve_scope(request.user).value}"
                if not isinstance(entry, dict) or entry.get("task_id") != str(task.task_id):
                    return Response({"error": "确认已过期或不属于当前任务"}, status=status.HTTP_403_FORBIDDEN)
                if entry.get("context_sig") != expected_sig:
                    return Response({"error": "确认已过期或不属于当前用户或范围"}, status=status.HTTP_403_FORBIDDEN)
                tool = ToolRegistry.get_tool_for_user(entry.get("tool_name"), request.user)
                if tool is None:
                    return Response({"error": "确认工具不可用"}, status=status.HTTP_404_NOT_FOUND)
                task_id = task.task_id
                tool_name = entry.get("tool_name")
                user_query = entry.get("user_query", "")
                allowed_replay_fields = _replay_allowed_fields(tool)
                draft_metadata = entry.get("draft") if isinstance(entry.get("draft"), dict) else {}
                metadata_fields = draft_metadata.get("fields") if isinstance(draft_metadata.get("fields"), dict) else draft_metadata
                operation_id = metadata_fields.get("operation_id") if isinstance(metadata_fields, dict) else None
                requested_operation_id = request.data.get("operation_id")
                if not operation_id or (requested_operation_id is not None and requested_operation_id != operation_id):
                    return Response({"error": "确认操作不匹配"}, status=status.HTTP_403_FORBIDDEN)
                validation_error_holder = []
                reject_holder = []

                def validate_and_prepare(claimed):
                    if not isinstance(claimed, dict):
                        return None
                    if (
                        claimed.get("task_id") != str(task_id)
                        or claimed.get("context_sig") != expected_sig
                        or claimed.get("tool_name") != tool_name
                    ):
                        validation_error_holder.append("确认令牌绑定不匹配")
                        return None
                    claimed_metadata = claimed.get("draft") if isinstance(claimed.get("draft"), dict) else {}
                    claimed_metadata_fields = claimed_metadata.get("fields") if isinstance(claimed_metadata.get("fields"), dict) else claimed_metadata
                    claimed_operation_id = claimed_metadata_fields.get("operation_id") if isinstance(claimed_metadata_fields, dict) else None
                    if claimed_operation_id != operation_id:
                        validation_error_holder.append("确认操作不匹配")
                        return None
                    claimed_draft = claimed_metadata
                    claimed_fields = claimed_draft.get("fields") if isinstance(claimed_draft.get("fields"), dict) else claimed_draft
                    candidate_fields = copy.deepcopy(_filter_replay_fields(claimed_fields, allowed_replay_fields))
                    event_bus = PersistentEventBus(agent_task_id=str(task_id))
                    pre_context = ToolContext(
                        user=request.user, scope=resolve_scope(request.user), task_id=task_id,
                        event_bus=event_bus, replay=True,
                        draft=_safe_replay_draft(claimed_draft, candidate_fields),
                    )
                    pre_result = apply_pre_execute_hooks(
                        tool, pre_context, candidate_fields, excluded_hook_names={"confirmation"},
                    )
                    if isinstance(pre_result, Reject):
                        reject_holder.append(pre_result)
                        return None
                    if isinstance(pre_result, dict):
                        candidate_fields.update(_filter_replay_fields(pre_result, allowed_replay_fields))
                    candidate_fields["operation_id"] = operation_id
                    error = _validate_replay_fields(tool, candidate_fields)
                    if error:
                        validation_error_holder.append(error)
                        return None
                    if getattr(tool, "name", None) == "agent_notify":
                        from django.contrib.auth import get_user_model
                        users = list(get_user_model().objects.filter(id__in=candidate_fields["recipient_ids"]))
                        if len(users) != len(candidate_fields["recipient_ids"]):
                            validation_error_holder.append("确认收件人参数无效")
                            return None
                        scope_error = tool._validate_scope(candidate_fields["scope"], {"user": request.user}, pre_context)
                        if scope_error:
                            validation_error_holder.append(scope_error)
                            return None
                        scope_error = tool._validate_users_scope(users, request.user, candidate_fields["scope"])
                        if scope_error:
                            validation_error_holder.append(scope_error)
                            return None
                        candidate_fields = {
                            **candidate_fields,
                            "title": candidate_fields["title"].strip(),
                            "content": candidate_fields["content"].strip(),
                        }
                    return {**claimed, "draft": _safe_replay_draft(claimed_draft, candidate_fields), "fields": candidate_fields}

                try:
                    claimed = consume_confirmation_draft(token, validator=validate_and_prepare)
                except ConfirmationDraftConsumeError:
                    return Response({"error": "确认服务暂不可用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                if reject_holder:
                    pre_result = reject_holder[0]
                    error_code = pre_result.error_code or "confirmation_rejected"
                    response_data = {"error": "确认操作未通过，请稍后重试", "error_code": error_code}
                    if pre_result.retry_after is not None:
                        response_data["retry_after"] = pre_result.retry_after
                    reject_status = status.HTTP_429_TOO_MANY_REQUESTS if error_code == "rate_limit_exceeded" else status.HTTP_403_FORBIDDEN
                    return Response(response_data, status=reject_status)
                if validation_error_holder:
                    return Response({"error": validation_error_holder[0], "error_code": "invalid_confirmation_params"}, status=status.HTTP_400_BAD_REQUEST)
                if claimed is None:
                    return Response({"error": "确认已被使用"}, status=status.HTTP_409_CONFLICT)
                final_draft = claimed["draft"]
                fields = claimed["fields"]
                recipient_ids = fields.get("recipient_ids")
                resolved_users = []
                if isinstance(recipient_ids, list):
                    from django.contrib.auth import get_user_model
                    resolved_users = list(get_user_model().objects.filter(id__in=recipient_ids))
        except AgentTask.DoesNotExist:
            return Response({"error": "任务不存在"}, status=status.HTTP_404_NOT_FOUND)

        event_bus = PersistentEventBus(agent_task_id=str(task_id))
        # 工具执行在事务提交后进行，避免 SQLite 写锁跨线程冲突。
        context = ToolContext(
            user=request.user,
            scope=resolve_scope(request.user),
            task_id=task_id,
            event_bus=event_bus,
            confirmed=True,
            draft={**final_draft, "_resolved_users": resolved_users},
        )
        try:
            result = execute_guarded(tool, user_query, context=context, params=fields)
            result = apply_post_execute_hooks(tool, result, context)
        except Exception as exc:
            logger.exception("确认工具执行失败: task_id=%s", task_id)
            apply_failure_hooks(tool, exc, context)
            event_bus.emit("subtask.tool_result", {
                "task_id": str(task_id), "status": "failed", "operation_id": operation_id,
                "error": "确认操作执行失败", "phase": "confirm", "operation": tool_name,
            })
            return Response({"found": False, "message": "确认操作执行失败，请稍后重试"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        event_bus.emit("user.intervention", {
            "task_id": str(task_id), "status": "confirmed", "operation_id": operation_id,
            "operation": tool_name, "phase": "confirm",
        })
        return Response({"result": public_tool_result(result, tool_name), "status": "confirmed", "task_id": str(task_id)})

    @action(detail=True, methods=["POST"])
    def intervene(self, request, pk=None):
        """POST /api/smart-assistant/tasks/{task_id}/intervene/ 用户介入。"""
        try:
            task = AgentTask.objects.get(task_id=pk, user=request.user)
        except AgentTask.DoesNotExist:
            return Response({"error": "任务不存在"}, status=status.HTTP_404_NOT_FOUND)
        action_type = request.data.get("action")
        if action_type not in ["pause", "resume", "cancel"]:
            return Response({"error": "action 必须是 pause / resume / cancel"}, status=status.HTTP_400_BAD_REQUEST)
        from ..tasks import dispatch_agent_task
        with transaction.atomic():
            task = AgentTask.objects.select_for_update().get(task_id=pk, user=request.user)
            if action_type == "pause":
                if task.status != "running":
                    return Response({"error": "只有运行中的任务可以暂停"}, status=status.HTTP_400_BAD_REQUEST)
                task.status = "paused"
                task.save(update_fields=["status"])
            elif action_type == "resume":
                if task.status != "paused":
                    return Response({"error": "只有暂停的任务可以恢复"}, status=status.HTTP_400_BAD_REQUEST)
                transaction.on_commit(lambda: dispatch_agent_task(task))
            else:
                if task.status in ["completed", "failed", "partial", "cancelled"]:
                    return Response({"error": f"任务状态为 {task.status},无法取消"}, status=status.HTTP_400_BAD_REQUEST)
                task.status = "cancelled"
                task.save(update_fields=["status"])
                from ..tasks import _schedule_agent_task_notification
                _schedule_agent_task_notification(task, "cancelled", transaction)
        return Response({"status": task.status})

    @action(detail=True, methods=["GET"])
    def stream(self, request, pk=None):
        """GET /api/smart-assistant/tasks/{task_id}/stream/

        SSE 实时进度推送
        """
        try:
            task = AgentTask.objects.get(task_id=pk, user=request.user)
        except AgentTask.DoesNotExist:
            return Response({"error": "任务不存在"}, status=status.HTTP_404_NOT_FOUND)

        def event_stream():
            raw_last_seq = request.query_params.get("last_seq", "0")
            try:
                last_seq = int(raw_last_seq)
            except (TypeError, ValueError):
                last_seq = 0
            last_seq = max(0, min(last_seq, 2_147_483_647))
            timeout = 60
            start_time = time.time()
            last_heartbeat = start_time
            terminal_statuses = {"completed", "failed", "partial", "cancelled", "paused"}
            timed_out = True

            while time.time() - start_time < timeout:
                events = (
                    AgentEvent.objects.filter(task=task, sequence__gt=last_seq)
                    .select_related("subtask")
                    .order_by("sequence")
                )

                for event in events:
                    data = {
                        "type": event.event_type,
                        "sequence": event.sequence,
                        "subtask_id": event.subtask_id if event.subtask else None,
                        "payload": _safe_event_payload(event),
                        "timestamp": event.created_at.isoformat(),
                    }
                    yield f"id: {event.sequence}\n{sse_event(data)}"
                    last_seq = event.sequence

                task.refresh_from_db(fields=["status"])
                if task.status in terminal_statuses:
                    terminal_sequence = last_seq + 1
                    done_data = {
                        "type": "done",
                        "task_id": str(task.task_id),
                        # synthetic 终态帧仅用于展示；最后一条持久化事件才是可恢复游标。
                        "sequence": terminal_sequence,
                        "status": task.status,
                        "synthetic": True,
                    }
                    yield f"id: {terminal_sequence}\n{sse_event(done_data)}"
                    timed_out = False
                    break

                now = time.time()
                if now - last_heartbeat >= 15:
                    yield ": ping\n\n"
                    last_heartbeat = now
                time.sleep(0.5)

            if timed_out:
                timeout_sequence = last_seq + 1
                timeout_data = {
                    "type": "timeout", "task_id": str(task.task_id),
                    "sequence": timeout_sequence, "status": task.status, "synthetic": True,
                }
                yield f"id: {timeout_sequence}\n{sse_event(timeout_data)}"

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # 禁用 nginx 缓冲
        return response

    @action(detail=True, methods=["GET"])
    def timeline(self, request, pk=None):
        """GET /api/smart-assistant/tasks/{task_id}/timeline/

        返回完整时间线(供前端渲染甘特图)
        """
        try:
            task = AgentTask.objects.get(task_id=pk, user=request.user)
        except AgentTask.DoesNotExist:
            return Response({"error": "任务不存在"}, status=status.HTTP_404_NOT_FOUND)

        # R5-B5: select_related 一次取齐 subtask FK,避免序列化时按事件逐条回表(N+1)
        events = AgentEvent.objects.filter(task=task).select_related("subtask").order_by("sequence")
        subtasks = AgentSubTask.objects.filter(task=task).order_by("subtask_id")

        timeline = []
        for event in events:
            item = _safe_event_payload(event)
            item.update(
                {
                    "sequence": event.sequence,
                    "event_type": event.event_type,
                    "subtask": event.subtask_id if event.subtask else None,
                    "subtask_id": event.subtask_id if event.subtask else None,
                }
            )
            timeline.append(item)

        return Response(
            {
                "task": {
                    "task_id": str(task.task_id),
                    "status": task.status,
                    "objective": _sanitize_text(task.objective or ""),
                },
                "subtasks": [
                    {
                        "subtask_id": subtask.subtask_id,
                        "status": subtask.status,
                        "role": subtask.role,
                        "objective": _sanitize_text(subtask.objective or ""),
                    }
                    for subtask in subtasks
                ],
                "timeline": timeline,
            }
        )
