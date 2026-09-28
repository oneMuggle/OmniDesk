"""知识自动入库管理接口（S4-2，仅智能助手管理员）。

- ``GET knowledge-sources/summary/``：是否已配置、按来源 × 状态统计、最近 20 条失败；
- ``POST knowledge-sources/reconcile/``：立即对账（Celery 异步）；
- ``POST knowledge-sources/<id>/retry/``：清零失败次数后重新入队。
"""

from __future__ import annotations

from django.db.models import Count
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from observability import get_logger

from ..knowledge.config import ingest_dataset_id, is_enabled
from ..models import KnowledgeSource
from ..permissions import IsSmartAssistantAdmin

logger = get_logger(__name__, "smart_assistant")

RECENT_FAILURES = 20


class KnowledgeSourceSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = KnowledgeSource
        fields = [
            "id",
            "source_type",
            "source_type_display",
            "source_id",
            "title",
            "status",
            "status_display",
            "attempts",
            "last_error",
            "ingested_at",
            "updated_at",
        ]


class KnowledgeSourceViewSet(viewsets.GenericViewSet):
    permission_classes = [IsSmartAssistantAdmin]
    serializer_class = KnowledgeSourceSerializer
    queryset = KnowledgeSource.objects.all()

    @action(detail=False, methods=["get"])
    def summary(self, request):
        counts = {code: {s: 0 for s, _ in KnowledgeSource.STATUS_CHOICES} for code, _ in KnowledgeSource.TYPE_CHOICES}
        for row in KnowledgeSource.objects.values("source_type", "status").annotate(n=Count("id")):
            counts.setdefault(row["source_type"], {})[row["status"]] = row["n"]
        failures = KnowledgeSource.objects.filter(status=KnowledgeSource.STATUS_FAILED).order_by("-updated_at")
        return Response(
            {
                "enabled": is_enabled(),
                "dataset_configured": bool(ingest_dataset_id()),
                "source_types": [{"value": c, "label": label} for c, label in KnowledgeSource.TYPE_CHOICES],
                "statuses": [{"value": c, "label": label} for c, label in KnowledgeSource.STATUS_CHOICES],
                "counts": counts,
                "failures": self.get_serializer(failures[:RECENT_FAILURES], many=True).data,
            }
        )

    @action(detail=False, methods=["post"])
    def reconcile(self, request):
        if not is_enabled():
            return Response({"detail": "自动入库未配置。", "code": "ingest_disabled"}, status=status.HTTP_409_CONFLICT)
        from ..tasks import reconcile_knowledge_sources

        try:
            reconcile_knowledge_sources.delay()
        except Exception as exc:
            logger.warning("知识入库对账入队失败: type=%s", type(exc).__name__)
            return Response({"detail": "任务队列不可用，请稍后再试。"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"queued": True}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        record = self.get_object()
        if not is_enabled():
            return Response({"detail": "自动入库未配置。", "code": "ingest_disabled"}, status=status.HTTP_409_CONFLICT)
        from ..tasks import sync_knowledge_source

        record.attempts = 0
        record.save(update_fields=["attempts", "updated_at"])
        try:
            sync_knowledge_source.delay(record.source_type, record.source_id)
        except Exception as exc:
            logger.warning("知识入库重试入队失败: type=%s", type(exc).__name__)
            return Response({"detail": "任务队列不可用，请稍后再试。"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(self.get_serializer(record).data, status=status.HTTP_202_ACCEPTED)
