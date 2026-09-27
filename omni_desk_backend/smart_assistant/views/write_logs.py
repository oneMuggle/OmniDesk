from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from observability import get_logger

from ..models import AgentWriteLog
from ..writes.revert import RevertConflict, get_revert_handler

logger = get_logger(__name__, "smart_assistant")

#: 允许撤销的原始操作类型；是否真能撤销由各目标模型的处理器决定
_REVERTIBLE_OPERATIONS = {"create", "update", "delete"}


class AgentWriteLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentWriteLog
        fields = [
            "id",
            "task",
            "session_id",
            "tool_name",
            "target_model",
            "target_pk",
            "operation",
            "before",
            "after",
            "revert_of",
            "reverted_at",
            "reverted_by",
            "created_at",
        ]
        read_only_fields = fields


class AgentWriteLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AgentWriteLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = AgentWriteLog.objects.filter(user=self.request.user).select_related("task", "revert_of")
        task_id = self.request.query_params.get("task_id")
        if task_id:
            queryset = queryset.filter(task__task_id=task_id)
        return queryset

    @action(detail=True, methods=["post"])
    def revert(self, request, pk=None):
        """撤销一次 AI 写操作：按 target_model 分发给已登记的处理器（S3-1）。"""
        with transaction.atomic():
            # The owner filter is deliberately inside the row lock: neither an
            # ID leak nor a concurrent second revert is possible.
            log = self.get_queryset().select_for_update().filter(pk=pk).first()
            if log is None:
                return Response({"detail": "写操作日志不存在。"}, status=status.HTTP_404_NOT_FOUND)
            if log.operation not in _REVERTIBLE_OPERATIONS:
                return Response({"detail": "该操作类型不支持回滚。"}, status=status.HTTP_409_CONFLICT)
            if log.reverted_at is not None:
                return Response({"detail": "该写操作已回滚。"}, status=status.HTTP_409_CONFLICT)
            handler = get_revert_handler(log.target_model)
            if handler is None:
                return Response({"detail": "暂不支持该目标模型。"}, status=status.HTTP_409_CONFLICT)
            try:
                # 保存点：处理器中途失败时，它已做的修改一并回滚
                with transaction.atomic():
                    result = handler.revert(log, request.user)
            except RevertConflict as exc:
                body = {"detail": exc.detail}
                if exc.current is not None:
                    body["current"] = exc.current
                return Response(body, status=status.HTTP_409_CONFLICT)
            revert = AgentWriteLog.objects.create(
                task=log.task,
                session_id=log.session_id,
                user=request.user,
                tool_name="write_log.revert",
                target_model=log.target_model,
                target_pk=result.target_pk,
                operation=result.operation,
                before=result.before,
                after=result.after,
                revert_of=log,
            )
            log.reverted_at = timezone.now()
            log.reverted_by = request.user
            log.save(update_fields=["reverted_at", "reverted_by"])
        logger.info(
            "write_log.reverted",
            extra={
                "event": "write_log.reverted",
                "write_log_id": log.pk,
                "target_model": log.target_model,
                "user_id": request.user.pk,
            },
        )
        return Response(AgentWriteLogSerializer(revert).data)
