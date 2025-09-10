from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import Sensor, SensorMovement, CalibrationReminder, SensorCategory, StorageLocation
from .serializers import SensorSerializer, SensorMovementSerializer, CalibrationReminderSerializer, SensorCategorySerializer, StorageLocationSerializer
from users.permissions import IsAdminOrManager, IsAdminOrManagerOrReadOnly # 假设有这些权限类

class SensorViewSet(viewsets.ModelViewSet):
    queryset = Sensor.objects.all()
    serializer_class = SensorSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'sensor_category__name', 'manufacturer', 'serial_number', 'location__name']
    search_fields = ['serial_number', 'sensor_category__name', 'manufacturer']
    ordering_fields = ['serial_number', 'sensor_category__name', 'production_date', 'last_calibration_date', 'next_calibration_date']

    @action(detail=False, methods=['get'], url_path='due-for-calibration')
    def due_for_calibration(self, request):
        """
        获取即将到期或已过期的校准传感器列表。
        查询参数：
        days_ahead: 提前多少天提醒 (默认为7天)
        """
        days_ahead = int(request.query_params.get('days_ahead', 7))
        today = timezone.now().date()
        remind_threshold_date = today + timedelta(days=days_ahead)

        # 筛选出 next_calibration_date 在提醒阈值内，或者已经过期的传感器
        # 并且当前状态不是 'under_calibration' 或 'retired'
        sensors = self.queryset.filter(
            models.Q(last_calibration_date__isnull=False) &
            models.Q(
                models.Q(
                    last_calibration_date__date__lte=today - timedelta(days=models.F('calibration_interval_days'))
                ) | # 已经过期
                models.Q(
                    last_calibration_date__date__lte=remind_threshold_date - timedelta(days=models.F('calibration_interval_days'))
                ) # 在提醒期内
            )
        ).exclude(status__in=['under_calibration', 'retired']).distinct()

        serializer = self.get_serializer(sensors, many=True)
        return Response(serializer.data)

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
