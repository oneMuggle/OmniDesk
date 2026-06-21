"""events.views.sequences — 人员顺序/领导顺序/节假日 ViewSet

拆分自原 events/views.py(Phase 3 优化)。包含:
- PersonnelSequenceViewSet: 工作日人员顺序
- LeaderSequenceViewSet: 值班领导顺序
- HolidayViewSet: 节假日管理
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets

from users.permissions import IsAdminOrManagerOrReadOnly

from ..models import Holiday, LeaderSequence, PersonnelSequence
from ..serializers import HolidaySerializer, LeaderSequenceSerializer, PersonnelSequenceSerializer


class PersonnelSequenceViewSet(viewsets.ModelViewSet):
    """人员顺序视图集"""

    queryset = PersonnelSequence.objects.all()
    serializer_class = PersonnelSequenceSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


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
