import logging

from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, status, viewsets
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

logger = logging.getLogger(__name__)

class SensorViewSet(viewsets.ModelViewSet):
    queryset = Sensor.objects.select_related('sensor_category', 'location')
    serializer_class = SensorSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]  # 之前为 AllowAny，已收紧
class SensorMovementViewSet(viewsets.ModelViewSet):
    queryset = SensorMovement.objects.all()
    serializer_class = SensorMovementSerializer
    permission_classes = [IsAdminOrManager] # 只有管理员和经理可以管理出入库
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sensor', 'movement_type', 'operator', 'movement_date']
    ordering_fields = ['movement_date']

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save(operator=self.request.user)
            sensor = instance.sensor
            quantity = instance.quantity

            if instance.movement_type == 'in':
                sensor.current_quantity += quantity
                sensor.status = 'in_stock'
            elif instance.movement_type == 'out':
                if sensor.current_quantity < quantity:
                    raise serializers.ValidationError("出库数量不能大于当前库存数量。")
                sensor.current_quantity -= quantity
                if sensor.current_quantity == 0:
                    sensor.status = 'retired' # 或者其他状态，例如 'out_of_stock'
                else:
                    sensor.status = 'in_use' # 如果还有库存，可以保持使用中或根据业务逻辑设置

            sensor.save()

    def perform_update(self, serializer):
        with transaction.atomic():
            old_instance = self.get_object()
            instance = serializer.save()

            sensor = instance.sensor
            old_quantity = old_instance.quantity
            new_quantity = instance.quantity
            old_movement_type = old_instance.movement_type
            new_movement_type = instance.movement_type

            # Revert old quantity
            if old_movement_type == 'in':
                sensor.current_quantity -= old_quantity
            elif old_movement_type == 'out':
                sensor.current_quantity += old_quantity

            # Apply new quantity
            if new_movement_type == 'in':
                sensor.current_quantity += new_quantity
            elif new_movement_type == 'out':
                if sensor.current_quantity < new_quantity:
                    raise serializers.ValidationError("出库数量不能大于当前库存数量。")
                sensor.current_quantity -= new_quantity

            # Update status based on new quantity and movement type
            if sensor.current_quantity == 0:
                sensor.status = 'retired'
            elif new_movement_type == 'in':
                sensor.status = 'in_stock'
            elif new_movement_type == 'out':
                sensor.status = 'in_use'

            sensor.save()

class SensorCategoryViewSet(viewsets.ModelViewSet):
    queryset = SensorCategory.objects.all()
    serializer_class = SensorCategorySerializer
    permission_classes = [IsAdminOrManagerOrReadOnly] # 允许非管理员查看类别

class SensorCalibrationViewSet(viewsets.ModelViewSet):
    queryset = SensorCalibration.objects.all()
    serializer_class = SensorCalibrationSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly] # 允许非管理员查看校准记录
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sensor', 'calibration_date', 'calibrated_by', 'reviewed_by']
    ordering_fields = ['calibration_date', 'sensor__serial_number']

class StorageLocationViewSet(viewsets.ModelViewSet):
    queryset = StorageLocation.objects.all()
    serializer_class = StorageLocationSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly] # 允许非管理员查看位置

class CalibrationReminderViewSet(viewsets.ModelViewSet):
    queryset = CalibrationReminder.objects.all()
    serializer_class = CalibrationReminderSerializer
    permission_classes = [IsAdminOrManager] # 只有管理员和经理可以管理提醒
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sensor', 'is_sent', 'remind_date']
    ordering_fields = ['remind_date']

    @action(detail=True, methods=['post'], url_path='mark-as-sent')
    def mark_as_sent(self, request, pk=None):
        """
        标记校准提醒为已发送。
        """
        reminder = self.get_object()
        if not reminder.is_sent:
            reminder.is_sent = True
            reminder.sent_date = timezone.now()
            reminder.save()
            return Response({'status': 'reminder marked as sent'}, status=status.HTTP_200_OK)
        return Response({'status': 'reminder already sent'}, status=status.HTTP_200_OK)
