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
import uuid

from django.db import transaction
from django.http import StreamingHttpResponse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..agents.supervisor import Supervisor
from ..agent.sse_contract import sse_event
from ..models import AgentEvent, AgentSubTask, AgentTask
from llm_service.router import get_router


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


class AgentSubTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentSubTask
        fields = [
            "subtask_id",
            "role",
            "objective",
            "status",
            "depends_on",
            "inputs",
            "output",
            "tokens_used",
            "started_at",
            "completed_at",
            "retry_count",
            "error_message",
        ]


class AgentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentEvent
        fields = ["sequence", "event_type", "subtask", "payload", "created_at"]


class AgentTaskSerializer(serializers.ModelSerializer):
    subtasks = AgentSubTaskSerializer(many=True, read_only=True)

    class Meta:
        model = AgentTask
        fields = [
            "task_id",
            "objective",
            "execution_mode",
            "status",
            "task_packet",
            "global_budget",
            "tokens_used",
            "started_at",
            "completed_at",
            "final_output",
            "created_at",
            "updated_at",
            "subtasks",
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
                    "plan": task.task_packet,
                },
                status=status.HTTP_201_CREATED,
            )

        except ValueError as e:
            return Response(
                {"error": f"Supervisor 无法生成任务计划: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"任务创建失败: {str(e)}"},
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

        from ..tasks import execute_agent_task

        with transaction.atomic():
            task = AgentTask.objects.select_for_update().get(task_id=pk, user=request.user)
            if task.status != "pending":
                return Response(
                    {"error": f"任务状态为 {task.status},无法执行"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            transaction.on_commit(lambda: execute_agent_task.delay(str(task.task_id)))

        return Response({"status": "started", "task_id": str(task.task_id)})

    @action(detail=True, methods=["POST"])
    def intervene(self, request, pk=None):
        """POST /api/smart-assistant/tasks/{task_id}/intervene/

        用户介入(暂停/恢复/取消)
        """
        try:
            task = AgentTask.objects.get(task_id=pk, user=request.user)
        except AgentTask.DoesNotExist:
            return Response({"error": "任务不存在"}, status=status.HTTP_404_NOT_FOUND)

        action_type = request.data.get("action")
        if action_type not in ["pause", "resume", "cancel"]:
            return Response(
                {"error": "action 必须是 pause / resume / cancel"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action_type = request.data.get("action")
        if action_type not in ["pause", "resume", "cancel"]:
            return Response(
                {"error": "action 必须是 pause / resume / cancel"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from ..tasks import execute_agent_task

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
                # 保持 paused，交由 worker 在锁内原子抢占为 running，避免伪恢复。
                transaction.on_commit(lambda: execute_agent_task.delay(str(task.task_id)))
            elif action_type == "cancel":
                if task.status in ["completed", "failed", "cancelled"]:
                    return Response({"error": f"任务状态为 {task.status},无法取消"}, status=status.HTTP_400_BAD_REQUEST)
                task.status = "cancelled"
                task.save(update_fields=["status"])

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
                        "payload": event.payload if isinstance(event.payload, dict) else {},
                        "timestamp": event.created_at.isoformat(),
                    }
                    yield f"id: {event.sequence}\n{sse_event(data)}"
                    last_seq = event.sequence

                task.refresh_from_db(fields=["status"])
                if task.status in terminal_statuses:
                    yield sse_event(
                        {
                            "type": "done",
                            "task_id": str(task.task_id),
                            "sequence": last_seq,
                            "status": task.status,
                        }
                    )
                    timed_out = False
                    break

                now = time.time()
                if now - last_heartbeat >= 15:
                    yield ": ping\n\n"
                    last_heartbeat = now
                time.sleep(0.5)

            if timed_out:
                yield sse_event({"type": "timeout", "task_id": str(task.task_id), "sequence": last_seq})

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

        return Response(
            {
                "task": AgentTaskSerializer(task).data,
                "subtasks": AgentSubTaskSerializer(subtasks, many=True).data,
                "timeline": AgentEventSerializer(events, many=True).data,
            }
        )
