from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from memos.models import Memo
from ..models import AgentWriteLog


class AgentWriteLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentWriteLog
        fields = ["id", "task", "session_id", "tool_name", "target_model", "target_pk", "operation", "before", "after", "revert_of", "reverted_at", "reverted_by", "created_at"]
        read_only_fields = fields


class AgentWriteLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AgentWriteLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AgentWriteLog.objects.filter(user=self.request.user).select_related("task", "revert_of")

    @action(detail=True, methods=["post"])
    def revert(self, request, pk=None):
        with transaction.atomic():
            log = self.get_queryset().select_for_update().filter(pk=pk).first()
            if log is None:
                return Response({"detail": "写操作日志不存在。"}, status=status.HTTP_404_NOT_FOUND)
            if log.operation == "delete":
                return Response({"detail": "删除操作不可回滚。"}, status=status.HTTP_400_BAD_REQUEST)
            if log.reverted_at is not None:
                return Response({"detail": "该写操作已回滚。"}, status=status.HTTP_400_BAD_REQUEST)
            if log.target_model != "memos.Memo":
                return Response({"detail": "暂不支持该目标模型。"}, status=status.HTTP_400_BAD_REQUEST)
            memo = Memo.all_objects.select_for_update().filter(pk=log.target_pk, user=request.user).first()
            if memo is None:
                return Response({"detail": "目标备忘录不存在。"}, status=status.HTTP_404_NOT_FOUND)
            current = _memo_snapshot(memo)
            if log.operation == "create":
                if current != (log.after or {}):
                    return Response({"detail": "目标当前值已变化，无法安全回滚。", "current": current}, status=409)
                before = current
                memo.is_deleted = True
                memo.deleted_at = timezone.now()
                memo.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
            else:
                expected = log.after or {}
                if any(current.get(key) != value for key, value in expected.items()):
                    return Response({"detail": "目标当前值已变化，无法安全回滚。", "current": current}, status=409)
                before = current
                _apply_memo_snapshot(memo, log.before or {})
                memo.save(update_fields=["title", "content", "reminder_time", "is_deleted", "deleted_at", "updated_at"])
            revert = AgentWriteLog.objects.create(
                task=log.task, session_id=log.session_id, user=request.user,
                tool_name="write_log.revert", target_model=log.target_model, target_pk=log.target_pk,
                operation="revert", before=before, after=_memo_snapshot(memo), revert_of=log,
            )
            log.reverted_at = timezone.now()
            log.reverted_by = request.user
            log.save(update_fields=["reverted_at", "reverted_by"])
        return Response(AgentWriteLogSerializer(revert).data)


def _memo_snapshot(memo):
    return {
        "title": memo.title,
        "content": memo.content,
        "reminder_time": str(memo.reminder_time) if memo.reminder_time else None,
        "is_deleted": memo.is_deleted,
        "deleted_at": memo.deleted_at.isoformat() if memo.deleted_at else None,
    }


def _apply_memo_snapshot(memo, snapshot):
    memo.title = snapshot.get("title", memo.title)
    memo.content = snapshot.get("content", memo.content)
    memo.is_deleted = snapshot.get("is_deleted", memo.is_deleted)
    deleted_at = snapshot.get("deleted_at")
    if memo.is_deleted:
        memo.deleted_at = timezone.datetime.fromisoformat(deleted_at) if deleted_at else timezone.now()
    else:
        memo.deleted_at = None
    if snapshot.get("reminder_time"):
        from smart_assistant.tools.memo_write_tools import _parse_reminder_time
        memo.reminder_time = _parse_reminder_time(snapshot["reminder_time"])
    else:
        memo.reminder_time = None
