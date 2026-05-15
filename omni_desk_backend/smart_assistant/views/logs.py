from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import AgentLog
from .serializers import AgentLogSerializer


class AgentLogViewSet(mixins.ListModelMixin,
                      mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    """Agent 日志审计：列表（支持过滤）+ 详情"""
    serializer_class = AgentLogSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']

    def get_queryset(self):
        qs = AgentLog.objects.all()

        intent = self.request.query_params.get('intent')
        if intent:
            qs = qs.filter(intent=intent)

        user_id = self.request.query_params.get('user_id')
        if user_id and self.request.user.is_staff:
            qs = qs.filter(session__user_id=user_id)

        start = self.request.query_params.get('start_time')
        end = self.request.query_params.get('end_time')
        if start:
            qs = qs.filter(created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lte=end)

        keyword = self.request.query_params.get('keyword')
        if keyword:
            qs = qs.filter(
                Q(user_query__icontains=keyword) |
                Q(llm_response__icontains=keyword)
            )

        return qs
