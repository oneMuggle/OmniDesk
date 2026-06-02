from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q, Avg, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import AgentLog, KnowledgeDataset


class StatsViewSet(viewsets.ViewSet):
    """运营统计接口"""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def overview(self, request):
        """GET /api/smart-assistant/stats/overview/ — 总体统计"""
        days = int(request.query_params.get("days", 30))
        since = timezone.now() - timedelta(days=days)

        logs = AgentLog.objects.filter(created_at__gte=since)
        total_conversations = logs.count()
        active_users = logs.values("session__user").distinct().count()
        intents = logs.values("intent").annotate(count=Count("intent")).order_by("-count")
        tools = logs.values("tool_used").annotate(count=Count("tool_used")).order_by("-count")

        # Token 和成本统计
        total_tokens = logs.aggregate(total=Sum("total_tokens"))["total"] or 0
        total_cost = logs.aggregate(total=Sum("estimated_cost"))["total"] or 0
        avg_response_time = logs.aggregate(avg=Avg("response_time_ms"))["avg"]

        # 工具成功率
        tool_success_count = logs.filter(tool_success=True).count()
        tool_total_count = logs.filter(tool_used__isnull=False).exclude(tool_used="").count()
        tool_success_rate = round(tool_success_count / tool_total_count * 100, 1) if tool_total_count > 0 else 0

        # 用户反馈
        feedback_up = logs.filter(user_feedback="up").count()
        feedback_down = logs.filter(user_feedback="down").count()

        return Response(
            {
                "period_days": days,
                "total_conversations": total_conversations,
                "active_users": active_users,
                "total_tokens": total_tokens,
                "total_cost": str(total_cost),
                "avg_response_time_ms": round(avg_response_time or 0),
                "tool_success_rate": tool_success_rate,
                "feedback_up": feedback_up,
                "feedback_down": feedback_down,
                "intent_breakdown": {item["intent"]: item["count"] for item in intents},
                "tool_breakdown": {item["tool_used"]: item["count"] for item in tools if item["tool_used"]},
                "top_questions": list(
                    AgentLog.objects.filter(created_at__gte=since)
                    .values("user_query")
                    .annotate(count=Count("user_query"))
                    .order_by("-count")[:10]
                ),
                "unrecognized": logs.filter(intent="general_chat").count(),
            }
        )

    @action(detail=False, methods=["get"])
    def daily(self, request):
        """GET /api/smart-assistant/stats/daily/ — 每日趋势"""
        days = int(request.query_params.get("days", 30))
        since = timezone.now() - timedelta(days=days)

        daily_stats = (
            AgentLog.objects.filter(created_at__gte=since)
            .extra(select={"date": "DATE(created_at)"})
            .values("date")
            .annotate(
                conversations=Count("id"),
                tool_calls=Count("id", filter=Q(tool_used__isnull=False) & ~Q(tool_used="")),
                total_tokens=Sum("total_tokens"),
                avg_response_time_ms=Avg("response_time_ms"),
            )
            .order_by("date")
        )

        return Response(
            {
                "daily_stats": list(daily_stats),
            }
        )

    @action(detail=False, methods=["get"], url_path="datasets")
    def datasets(self, request):
        """GET /api/smart-assistant/stats/datasets/ — 知识库数据集列表"""
        datasets = KnowledgeDataset.objects.filter(is_active=True).order_by("priority", "name")
        return Response(
            {
                "datasets": [
                    {
                        "id": ds.id,
                        "name": ds.name,
                        "description": ds.description,
                        "tags": ds.tags,
                        "document_count": ds.document_count,
                        "priority": ds.priority,
                    }
                    for ds in datasets
                ]
            }
        )
