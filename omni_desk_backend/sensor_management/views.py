import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.permissions import IsAdminOrManager, IsAdminOrManagerOrReadOnly  # 假设有这些权限类

from .models import CalibrationReminder, Sensor, SensorCalibration, SensorCategory, SensorMovement, StorageLocation
from .serializers import (
    CalibrationReminderSerializer,
    SensorCalibrationSerializer,
    SensorCategorySerializer,
    SensorMovementSerializer,
    SensorSerializer,
    StorageLocationSerializer,
)

from .services.inventory_service import InventoryService, CalibrationService

logger = logging.getLogger(__name__)


class SensorViewSet(viewsets.ModelViewSet):
    queryset = Sensor.objects.select_related("sensor_category", "location")
    serializer_class = SensorSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]  # 之前为 AllowAny，已收紧


class SensorMovementViewSet(viewsets.ModelViewSet):
    queryset = SensorMovement.objects.select_related("operator", "sensor")
    serializer_class = SensorMovementSerializer
    permission_classes = [IsAdminOrManager]  # 只有管理员和经理可以管理出入库
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["sensor", "movement_type", "operator", "movement_date"]
    ordering_fields = ["movement_date"]

    def perform_create(self, serializer):
        instance = serializer.save(operator=self.request.user)
        InventoryService.process_movement(instance)

    def perform_update(self, serializer):
        old_instance = self.get_object()
        new_instance = serializer.save()
        InventoryService.update_movement(old_instance, new_instance)


class SensorCategoryViewSet(viewsets.ModelViewSet):
    queryset = SensorCategory.objects.all()
    serializer_class = SensorCategorySerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]  # 允许非管理员查看类别


class SensorCalibrationViewSet(viewsets.ModelViewSet):
    queryset = SensorCalibration.objects.select_related("calibrated_by", "reviewed_by")
    serializer_class = SensorCalibrationSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]  # 允许非管理员查看校准记录
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["sensor", "calibration_date", "calibrated_by", "reviewed_by"]
    ordering_fields = ["calibration_date", "sensor__serial_number"]


class StorageLocationViewSet(viewsets.ModelViewSet):
    queryset = StorageLocation.objects.all()
    serializer_class = StorageLocationSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]  # 允许非管理员查看位置


class CalibrationReminderViewSet(viewsets.ModelViewSet):
    queryset = CalibrationReminder.objects.select_related("sensor")
    serializer_class = CalibrationReminderSerializer
    permission_classes = [IsAdminOrManager]  # 只有管理员和经理可以管理提醒
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["sensor", "is_sent", "remind_date"]
    ordering_fields = ["remind_date"]

    @action(detail=True, methods=["post"], url_path="mark-as-sent")
    def mark_as_sent(self, request, pk=None):
        """标记校准提醒为已发送。"""
        reminder = self.get_object()
        return Response(CalibrationService.mark_as_sent(reminder), status=status.HTTP_200_OK)
