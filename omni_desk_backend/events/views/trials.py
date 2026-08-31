"""events.views.trials — 试验/设备/时间段 ViewSet

拆分自原 events/views.py(Phase 3 优化)。包含:
- TrialViewSet: 试验 CRUD + 本周查询 + 时间段管理 + 导出
- EquipmentViewSet: 设备 CRUD
- TimeSlotViewSet: 时间段 CRUD + 批量创建
"""

from io import BytesIO

from observability import get_logger
from datetime import timedelta

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from openpyxl import Workbook
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.permissions import IsAdminOrManagerOrReadOnly

from ..models import Equipment, TimeSlot, Trial
from ..serializers import EquipmentSerializer, TimeSlotSerializer, TrialSerializer

logger = get_logger(__name__, "events.views.trials")


class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.select_related("trial").all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["trial", "start_time", "end_time"]

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        """批量创建时间段"""
        trial_id = request.data.get("trial")
        time_slots = request.data.get("time_slots", [])

        if not trial_id:
            return Response({"error": "trial is required"}, status=400)

        try:
            trial = Trial.objects.get(pk=trial_id)
        except Trial.DoesNotExist:
            return Response({"error": "trial not found"}, status=404)

        with transaction.atomic():
            new_slots = TimeSlot.objects.bulk_create(
                [
                    TimeSlot(
                        trial=trial,
                        start_time=slot["start_time"],
                        end_time=slot["end_time"],
                        description=slot.get("description", ""),
                    )
                    for slot in time_slots
                ]
            )
            trial.update_time_range()

        serializer = TimeSlotSerializer(new_slots, many=True)
        return Response(serializer.data, status=201)

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            instance.trial.update_time_range()

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                logger.debug("Starting update for time slot %s", serializer.instance.id)
                instance = serializer.save(update_fields=["start_time", "end_time", "description"])
                logger.debug("Updated time slot: %s to %s", instance.start_time, instance.end_time)

                trial = instance.trial
                logger.debug("Updating time range for trial %s", trial.id)
                trial.update_time_range()
                logger.debug("Finished updating trial %s time range", trial.id)
        except Exception as e:
            logger.error("Error updating time slot: %s", e, exc_info=True)
            raise

    def perform_destroy(self, instance):
        with transaction.atomic():
            trial = instance.trial
            instance.delete()
            trial.update_time_range()


class TrialViewSet(viewsets.ModelViewSet):
    queryset = Trial.objects.prefetch_related("equipments", "responsible_persons", "time_slots")
    serializer_class = TrialSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    # 使用 dict 显式声明每个字段支持的 lookup,
    # 否则 list 模式下 DjangoFilterBackend 不会自动开启 __gte/__lte 等查询。
    filterset_fields = {
        "status": ["exact"],
        "equipments": ["exact"],
        "responsible_persons": ["exact"],
        "start_date": ["exact", "gte", "lte"],
        "end_date": ["exact", "gte", "lte"],
        "time_slots__start_time": ["exact", "gte", "lte"],
        "time_slots__end_time": ["exact", "gte", "lte"],
    }
    ordering_fields = ["start_date", "end_date", "time_slots__start_time"]

    @action(detail=False, methods=["get"], url_path="this-week")
    def get_this_week_trials(self, request):
        """获取本周的试验日程。"""
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        queryset = (
            self.get_queryset()
            .filter(
                start_date__lte=end_of_week,
                end_date__gte=start_of_week,
            )
            .distinct()
        )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """导出当前过滤条件下的试验列表为 xlsx。

        URL: GET /api/events/trials/export/?format=xlsx&status=...&...
        复用 filterset_fields(状态、设备、负责人、起止日期),
        与 TrialsPage 列表视图的过滤语义保持一致。
        输出列:试验名称 / 状态(中文)/ 主开始时间 / 主结束时间。
        """
        queryset = self.filter_queryset(self.get_queryset())

        wb = Workbook()
        ws = wb.active
        ws.title = "试验列表"
        ws.append(["试验名称", "状态", "主开始时间", "主结束时间"])

        status_label_map = dict(Trial.STATUS_CHOICES)
        for trial in queryset:
            start_local = timezone.localtime(trial.start_date).replace(tzinfo=None) if trial.start_date else None
            end_local = timezone.localtime(trial.end_date).replace(tzinfo=None) if trial.end_date else None
            ws.append(
                [
                    trial.title,
                    status_label_map.get(trial.status, trial.status),
                    start_local,
                    end_local,
                ]
            )

        ws.column_dimensions["A"].width = 32
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 22
        ws.column_dimensions["D"].width = 22

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        today = timezone.now().date().isoformat()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="trials-{today}.xlsx"'
        return response

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("equipments", "responsible_persons", "time_slots")
        return queryset.order_by("-start_date")

    def perform_create(self, serializer):
        """原子化创建试验及其时间段"""
        time_periods = self.request.data.get("time_periods", [])

        with transaction.atomic():
            instance = serializer.save()
            instance.equipments.set(self.request.data.get("equipment_ids", []))
            instance.responsible_persons.set(self.request.data.get("responsible_person_ids", []))

            if time_periods:
                TimeSlot.objects.bulk_create(
                    [
                        TimeSlot(
                            trial=instance,
                            start_time=period["start_time"],
                            end_time=period["end_time"],
                            description=period.get("description", ""),
                        )
                        for period in time_periods
                    ]
                )
                instance.update_time_range()

    def perform_update(self, serializer):
        """原子化更新试验及其时间段"""
        current_version = serializer.instance.version
        if "version" in self.request.data:
            if self.request.data["version"] != current_version:
                raise serializers.ValidationError({"version": "数据已被其他用户修改，请刷新后重试"})

        serializer.save(version=current_version + 1)

    @action(detail=True, methods=["post", "patch"], url_path="update-time-slots")
    def update_time_slots(self, request, pk=None):
        """原子化更新时间段"""
        trial = self.get_object()
        time_periods = request.data

        with transaction.atomic():
            trial.time_slots.all().delete()

            new_slots = TimeSlot.objects.bulk_create(
                [
                    TimeSlot(
                        trial=trial,
                        start_time=period["start_time"],
                        end_time=period["end_time"],
                        description=period.get("description", ""),
                    )
                    for period in time_periods
                ]
            )
            trial.update_time_range()

        serializer = TimeSlotSerializer(new_slots, many=True)
        return Response(serializer.data, status=201)
