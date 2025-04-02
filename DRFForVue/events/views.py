from rest_framework import viewsets, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions, IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from .models import Trial
from .models import Trial, Personnel, Equipment, DocumentTemplate
from .serializers import TrialSerializer, PersonnelSerializer, EquipmentSerializer, DocumentTemplateSerializer, TimeSlotSerializer
from users.permissions import IsOwnerOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend

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
        time_slots = self.request.data.get('time_slots', [])
        
        with transaction.atomic():
            # 创建试验基础信息
            instance = serializer.save()
            
            # 处理关联关系
            instance.equipments.set(self.request.data.get('equipment_ids', []))
            instance.responsible_persons.set(self.request.data.get('responsible_person_ids', []))
            
            # 直接创建时间段（已通过外键关联）
            if time_slots:
                TimeSlot.objects.bulk_create([
                    TimeSlot(
                        trial=instance,
                        start_time=slot['start_time'],
                        end_time=slot['end_time'],
                        description=slot.get('description', '')
                    ) for slot in time_slots
                ])

    def perform_update(self, serializer):
        """原子化更新试验及其时间段"""
        time_slots = self.request.data.get('time_slots', [])
        instance = self.get_object()
        
        with transaction.atomic():
            # 先更新试验基本信息
            super().perform_update(serializer)
            
            # 清空原有时间段
            instance.time_slots.all().delete()
            
            # 创建新时间段
            if time_slots:
                TimeSlot.objects.bulk_create([
                    TimeSlot(
                        trial=instance,
                        start_time=slot['start_time'],
                        end_time=slot['end_time'],
                        description=slot.get('description', '')
                    ) for slot in time_slots
                ])

    @action(detail=True, methods=['patch'], url_path='update-time-slots')
    def update_time_slots(self, request, pk=None):
        """原子化更新时间槽"""
        trial = self.get_object()
        time_slots = request.data
        
        with transaction.atomic():
            # 删除原有时间段
            trial.time_slots.all().delete()
            
            # 创建新时间段
            TimeSlot.objects.bulk_create([
                TimeSlot(
                    trial=trial,
                    start_time=slot['start_time'],
                    end_time=slot['end_time'],
                    description=slot.get('description', '')
                ) for slot in time_slots
            ])
        
        return Response(status=204)
