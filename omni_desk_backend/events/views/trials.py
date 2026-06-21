"""events.views.trials — 试验/设备/时间段 ViewSet

拆分自原 events/views.py(Phase 3 优化)。包含:
- TrialViewSet: 试验 CRUD + 本周查询 + 时间段管理
- EquipmentViewSet: 设备 CRUD
- TimeSlotViewSet: 时间段 CRUD + 批量创建
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.permissions import IsAdminOrManagerOrReadOnly

from ..models import Equipment, TimeSlot, Trial
from ..serializers import EquipmentSerializer, TimeSlotSerializer, TrialSerializer

logger = logging.getLogger(__name__)


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

                transaction.on_commit(lambda: None)
        except Exception as e:
            logger.error("Error updating time slot: %s", e)
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
    filterset_fields = [
        "status",
        "equipments",
        "responsible_persons",
        "start_date",
        "end_date",
        "time_slots__start_time",
        "time_slots__end_time",
    ]
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
