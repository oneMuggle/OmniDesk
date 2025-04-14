from rest_framework import viewsets, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions, IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from .models import Trial, TimeSlot
from .models import Trial, Personnel, Equipment, DocumentTemplate
from .serializers import TrialSerializer, PersonnelSerializer, EquipmentSerializer, DocumentTemplateSerializer, TimeSlotSerializer
from users.permissions import IsOwnerOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend

class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['trial', 'start_time', 'end_time']

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """批量创建时间段"""
        trial_id = request.data.get('trial')
        time_slots = request.data.get('time_slots', [])
        
        if not trial_id:
            return Response({'error': 'trial is required'}, status=400)
        
        try:
            trial = Trial.objects.get(pk=trial_id)
        except Trial.DoesNotExist:
            return Response({'error': 'trial not found'}, status=404)

        with transaction.atomic():
            new_slots = TimeSlot.objects.bulk_create([
                TimeSlot(
                    trial=trial,
                    start_time=slot['start_time'],
                    end_time=slot['end_time'],
                    description=slot.get('description', '')
                ) for slot in time_slots
            ])
            trial.update_time_range()

        serializer = TimeSlotSerializer(new_slots, many=True)
        return Response(serializer.data, status=201)

    def perform_create(self, serializer):
        """创建时间段并自动更新关联试验的时间范围"""
        with transaction.atomic():
            instance = serializer.save()
            instance.trial.update_time_range()

    def perform_update(self, serializer):
        """更新时间段并自动更新关联试验的时间范围"""
        try:
            with transaction.atomic():
                print(f"Starting update for time slot {serializer.instance.id}")  # 调试日志
                # 保存时间段
                instance = serializer.save(update_fields=['start_time', 'end_time', 'description'])
                print(f"Updated time slot: {instance.start_time} to {instance.end_time}")  # 调试日志
                
                # 显式更新关联试验的时间范围
                trial = instance.trial
                print(f"Updating time range for trial {trial.id}")  # 调试日志
                trial.update_time_range()
                print(f"Finished updating trial {trial.id} time range")  # 调试日志
                
                # 确保数据已提交到数据库
                transaction.on_commit(lambda: None)
        except Exception as e:
            print(f"Error updating time slot: {str(e)}")
            raise

    def perform_destroy(self, instance):
        """删除时间段并自动更新关联试验的时间范围"""
        with transaction.atomic():
            trial = instance.trial
            instance.delete()
            trial.update_time_range()

class DocumentTemplateViewSet(viewsets.ModelViewSet):
    queryset = DocumentTemplate.objects.all()
    serializer_class = DocumentTemplateSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'experiment_type', 'created_at']

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name']

class ResponsiblePersonViewSet(viewsets.ModelViewSet):
    queryset = Personnel.objects.all()
    serializer_class = PersonnelSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'department', 'phone']

class TrialViewSet(viewsets.ModelViewSet):
    queryset = Trial.objects.prefetch_related(
        'equipments',
        'responsible_persons',
        'time_slots'
    ).all()
    serializer_class = TrialSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        'status',
        'equipments',
        'responsible_persons',
        'start_date',
        'end_date',
        'time_slots__start_time',
        'time_slots__end_time'
    ]
    ordering_fields = [
        'start_date',
        'end_date',
        'time_slots__start_time'
    ]

    def get_queryset(self):
        """查询集配置（参照设备管理视图）"""
        return super().get_queryset().order_by('-start_date')

    def perform_create(self, serializer):
        """原子化创建试验及其时间段"""
        time_periods = self.request.data.get('time_periods', [])
        
        with transaction.atomic():
            # 创建试验基础信息
            instance = serializer.save()
            
            # 处理关联关系
            instance.equipments.set(self.request.data.get('equipment_ids', []))
            instance.responsible_persons.set(self.request.data.get('responsible_person_ids', []))
            
            # 直接创建时间段（已通过外键关联）
            if time_periods:
                TimeSlot.objects.bulk_create([
                    TimeSlot(
                        trial=instance,
                        start_time=period['start_time'],
                        end_time=period['end_time'],
                        description=period.get('description', '')
                    ) for period in time_periods
                ])
                instance.update_time_range()  # 显式调用时间范围更新

    def perform_update(self, serializer):
        """原子化更新试验及其时间段"""
        time_periods = self.request.data.get('time_periods', [])
        instance = self.get_object()
        
        with transaction.atomic():
            # 乐观锁检查
            current_version = instance.version
            if 'version' in self.request.data:
                if self.request.data['version'] != current_version:
                    raise serializers.ValidationError(
                        {'version': '数据已被其他用户修改，请刷新后重试'}
                    )
            
            # 先更新试验基本信息并增加版本号
            serializer.save(version=current_version + 1)
            
            # 清空原有时间段
            instance.time_slots.all().delete()
            
            # 创建新时间段
            if time_periods:
                TimeSlot.objects.bulk_create([
                    TimeSlot(
                        trial=instance,
                        start_time=period['start_time'],
                        end_time=period['end_time'],
                        description=period.get('description', '')
                    ) for period in time_periods
                ])

    @action(detail=True, methods=['post', 'patch'], url_path='update-time-slots')
    def update_time_slots(self, request, pk=None):
        """原子化更新时间段"""
        trial = self.get_object()
        time_periods = request.data
        
        with transaction.atomic():
            # 删除原有时间段
            trial.time_slots.all().delete()
            
            # 创建新时间段
            new_slots = TimeSlot.objects.bulk_create([
                TimeSlot(
                    trial=trial,
                    start_time=period['start_time'],
                    end_time=period['end_time'],
                    description=period.get('description', '')
                ) for period in time_periods
            ])
            trial.update_time_range()  # 显式调用时间范围更新
        
        # 返回新创建的时间段数据
        serializer = TimeSlotSerializer(new_slots, many=True)
        return Response(serializer.data, status=201)
