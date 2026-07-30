"""events.views.sequences — 人员顺序/领导顺序/节假日 ViewSet

拆分自原 events/views.py(Phase 3 优化)。包含:
- PersonnelSequenceViewSet: 工作日人员顺序
- LeaderSequenceViewSet: 值班领导顺序
- HolidayViewSet: 节假日管理
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.response import Response

from personnel.models import Personnel
from users.permissions import IsAdminOrManagerOrReadOnly

from ..models import Holiday, LeaderSequence, PersonnelSequence
from ..serializers import HolidaySerializer, LeaderSequenceSerializer, PersonnelSequenceSerializer


class PersonnelSequenceViewSet(viewsets.ModelViewSet):
    """人员顺序视图集"""

    # prefetch 节假日人员 M2M,避免序列化器逐行查询 holiday_personnel
    queryset = PersonnelSequence.objects.prefetch_related("holiday_personnel")
    serializer_class = PersonnelSequenceSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]

    def list(self, request, *args, **kwargs):
        """列表场景批量预取 sequence 中的 Personnel,注入序列化器 context,消除逐行 N+1。"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        instances = page if page is not None else list(queryset)

        # sequence 是 JSONField 存的 personnel id 列表;聚合本页所有 id 一次性取回
        personnel_ids = set()
        for seq in instances:
            personnel_ids.update(seq.sequence or [])
        personnel_map = {p.id: p for p in Personnel.objects.filter(id__in=personnel_ids)}

        context = {**self.get_serializer_context(), "personnel_map": personnel_map}
        serializer = self.get_serializer(instances, many=True, context=context)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class LeaderSequenceViewSet(viewsets.ModelViewSet):
    """领导顺序视图集"""

    queryset = LeaderSequence.objects.all()
    serializer_class = LeaderSequenceSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["name", "start_date", "end_date"]

    def get_queryset(self):
        """按年份过滤节假日"""
        queryset = Holiday.objects.all()
        year = self.request.query_params.get("year")
        if year is not None:
            queryset = queryset.filter(start_date__year=year)
        return queryset
