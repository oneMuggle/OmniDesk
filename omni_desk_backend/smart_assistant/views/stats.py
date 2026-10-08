from collections import defaultdict
from datetime import timedelta

from django.utils import timezone
from django.db.models import Count, Q, Avg, Sum
from django.db.models.functions import TruncDate
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from smart_assistant.utils import percentile

from ..agent.conversation_context import FAILED_ANSWER_PREFIX, FAILED_ANSWER_STREAM_PREFIX
from ..models import AgentLog, KnowledgeDataset, LlmUsageDaily
from ..permissions import IsSmartAssistantAdmin


MIN_STATS_DAYS = 1
MAX_STATS_DAYS = 365
USAGE_APP_NAME = "smart_assistant"
UNKNOWN_MODEL_LABEL = "未记录"

# 失败答复（与 is_failed_answer 同口径：非流式「回答生成失败…」、流式「[错误] 回答生成失败…」）
FAILED_ANSWER_Q = Q(llm_response__startswith=FAILED_ANSWER_PREFIX) | Q(
    llm_response__startswith=FAILED_ANSWER_STREAM_PREFIX
)


def conversation_logs(qs):
    """只保留「一轮对话」级别的日志。

    AgentLog 里还混有工具级审计（AuditLogHook，不写响应时间）和工具链逐步记录
    （intent 以 ``chain:`` 开头）；成功率、延迟、按模型统计都只看对话本身。
    """
    return qs.filter(response_time_ms__isnull=False).exclude(intent__startswith="chain:")


def _rate(ok: int, total: int):
    return round(ok / total * 100, 1) if total else None


def _llm_call_stats(since_date):
    agg = LlmUsageDaily.objects.filter(date__gte=since_date, app_name=USAGE_APP_NAME).aggregate(
        calls=Sum("calls"), failed=Sum("failed_calls")
    )
    calls, failed = agg["calls"] or 0, agg["failed"] or 0
    return {
        "llm_calls": calls,
        "llm_failed_calls": failed,
        "llm_call_success_rate": _rate(calls, calls + failed),
    }


def _by_model(conv_logs):
    rows = (
        conv_logs.values("model_name")
        .annotate(
            conversations=Count("id"),
            failures=Count("id", filter=FAILED_ANSWER_Q),
            avg_response_time_ms=Avg("response_time_ms"),
            total_tokens=Sum("total_tokens"),
        )
        .order_by("-conversations")
    )
    latencies: dict = defaultdict(list)
    for model, ms in conv_logs.values_list("model_name", "response_time_ms"):
        latencies[model].append(ms)
    result = []
    for row in rows:
        model = row["model_name"]
        result.append(
            {
                "model": model or UNKNOWN_MODEL_LABEL,
                "conversations": row["conversations"],
                "answer_success_rate": _rate(row["conversations"] - row["failures"], row["conversations"]),
                "avg_response_time_ms": round(row["avg_response_time_ms"] or 0),
                "p95_response_time_ms": percentile(latencies[model], 95),
                "total_tokens": row["total_tokens"] or 0,
            }
        )
    return result


def _parse_days(request):
    raw_days = request.query_params.get("days", "30")
    try:
        days = int(raw_days)
    except (TypeError, ValueError):
        return None
    if not MIN_STATS_DAYS <= days <= MAX_STATS_DAYS:
        return None
    return days


class StatsViewSet(viewsets.ViewSet):
    """运营统计接口"""

    permission_classes = [IsSmartAssistantAdmin]

    @action(detail=False, methods=["get"])
    def overview(self, request):
        """GET /api/smart-assistant/stats/overview/ — 总体统计"""
        days = _parse_days(request)
        if days is None:
            return Response({"detail": "days 必须是 1 至 365 之间的整数。"}, status=status.HTTP_400_BAD_REQUEST)
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

        # 方案 5.6 S0：回答成功率、延迟分位、LLM 调用成功率、按模型分列（只看对话级日志）
        conv = conversation_logs(logs)
        conversation_count = conv.count()
        answer_failures = conv.filter(FAILED_ANSWER_Q).count()
        conv_latencies = list(conv.values_list("response_time_ms", flat=True))

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
                    .values("intent")
                    .annotate(count=Count("id"))
                    .order_by("-count")[:10]
                ),
                "unrecognized": logs.filter(intent="general_chat").count(),
                "conversation_count": conversation_count,
                "answer_failures": answer_failures,
                "answer_success_rate": _rate(conversation_count - answer_failures, conversation_count),
                "p50_response_time_ms": percentile(conv_latencies, 50),
                "p95_response_time_ms": percentile(conv_latencies, 95),
                **_llm_call_stats(since.date()),
                "by_model": _by_model(conv),
            }
        )

    @action(detail=False, methods=["get"])
    def daily(self, request):
        """GET /api/smart-assistant/stats/daily/ — 每日趋势"""
        days = _parse_days(request)
        if days is None:
            return Response({"detail": "days 必须是 1 至 365 之间的整数。"}, status=status.HTTP_400_BAD_REQUEST)
        since = timezone.now() - timedelta(days=days)

        daily_stats = (
            AgentLog.objects.filter(created_at__gte=since)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(
                conversations=Count("id"),
                tool_calls=Count("id", filter=Q(tool_used__isnull=False) & ~Q(tool_used="")),
                total_tokens=Sum("total_tokens"),
                avg_response_time_ms=Avg("response_time_ms"),
            )
            .order_by("date")
        )

        # 每日回答成功率与 P95（对话级日志）
        conv = conversation_logs(AgentLog.objects.filter(created_at__gte=since)).annotate(date=TruncDate("created_at"))
        per_day = {
            row["date"]: row
            for row in conv.values("date").annotate(
                conversations=Count("id"), failures=Count("id", filter=FAILED_ANSWER_Q)
            )
        }
        day_latencies: dict = defaultdict(list)
        for day, ms in conv.values_list("date", "response_time_ms"):
            day_latencies[day].append(ms)

        rows = []
        for row in daily_stats:
            day = per_day.get(row["date"])
            conversations = day["conversations"] if day else 0
            failures = day["failures"] if day else 0
            rows.append(
                {
                    **row,
                    "answer_success_rate": _rate(conversations - failures, conversations),
                    "p95_response_time_ms": percentile(day_latencies.get(row["date"], []), 95),
                }
            )

        return Response(
            {
                "daily_stats": rows,
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
