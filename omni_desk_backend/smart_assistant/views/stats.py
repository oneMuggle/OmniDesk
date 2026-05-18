from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import AgentLog, SmartAssistantSession


class StatsViewSet(viewsets.ViewSet):
    """运营统计接口"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """GET /api/smart-assistant/stats/overview/ — 总体统计"""
        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)

        logs = AgentLog.objects.filter(created_at__gte=since)
        total_conversations = logs.count()
        active_users = logs.values('session__user').distinct().count()
        intents = logs.values('intent').annotate(count=Count('intent')).order_by('-count')
        tools = logs.values('tool_used').annotate(count=Count('tool_used')).order_by('-count')

        return Response({
            'period_days': days,
            'total_conversations': total_conversations,
            'active_users': active_users,
            'intent_breakdown': {item['intent']: item['count'] for item in intents},
            'tool_breakdown': {item['tool_used']: item['count'] for item in tools if item['tool_used']},
            'top_questions': list(
                AgentLog.objects.filter(created_at__gte=since)
                .values('user_query')
                .annotate(count=Count('user_query'))
                .order_by('-count')[:10]
            ),
            'unrecognized': logs.filter(intent='general_chat').count(),
        })

    @action(detail=False, methods=['get'])
    def daily(self, request):
        """GET /api/smart-assistant/stats/daily/ — 每日趋势"""
        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)

        daily_stats = AgentLog.objects.filter(
            created_at__gte=since
        ).extra(
            select={'date': 'DATE(created_at)'}
        ).values('date').annotate(
            conversations=Count('id'),
            tool_calls=Count('id', filter=Q(tool_used__isnull=False) & ~Q(tool_used='')),
        ).order_by('date')

        return Response({
            'daily_stats': list(daily_stats),
        })
