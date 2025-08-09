from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework import viewsets, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from users.permissions import IsAdminOrManager, IsAdminOrManagerOrReadOnly
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
from .models import (
    Trial, TimeSlot, Personnel, Equipment, DocumentTemplate, Schedule, Announcement, UploadedImage
)
from .serializers import (
    TrialSerializer,
    PersonnelSerializer,
    EquipmentSerializer,
    DocumentTemplateSerializer,
    TimeSlotSerializer,
    ScheduleSerializer,
    AnnouncementSerializer,
    UploadedImageSerializer
)
from django_filters.rest_framework import DjangoFilterBackend

class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
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
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'experiment_type', 'created_at']

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class EquipmentViewSet(viewsets.ModelViewSet):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name']

class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer

    @action(detail=False, methods=['post'])
    def upsert(self, request):
        """创建或更新排班记录"""
        data = request.data
        if 'id' in data and data['id']:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=data, partial=True)
        else:
            serializer = self.get_serializer(data=data)
        
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['duty_date', 'duty_person', 'duty_leader']
    ordering_fields = ['duty_date']

    @action(detail=False, methods=['get'], url_path='by-date-range')
    def by_date_range(self, request):
        """按日期范围查询排班"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date or not end_date:
            return Response({'error': 'start_date and end_date are required'}, status=400)
            
        queryset = self.queryset.filter(
            duty_date__gte=start_date,
            duty_date__lte=end_date
        ).order_by('duty_date')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='bulk-update')
    def bulk_update(self, request):
        """批量更新排班"""
        schedules_data = request.data.get('schedules', [])
        
        with transaction.atomic():
            # 先删除原有排班
            if request.data.get('clear_existing', False):
                Schedule.objects.all().delete()
            
            # 创建新排班
            new_schedules = []
            for schedule_data in schedules_data:
                serializer = self.get_serializer(data=schedule_data)
                serializer.is_valid(raise_exception=True)
                new_schedules.append(Schedule(**serializer.validated_data))
            
            Schedule.objects.bulk_create(new_schedules)
        
        return Response({'status': 'success'}, status=201)

    def perform_create(self, serializer):
        """创建排班时检查日期是否已存在"""
        duty_date = serializer.validated_data.get('duty_date')
        override = self.request.data.get('override', False)
        
        if Schedule.objects.filter(duty_date=duty_date).exists():
            if override:
                # 覆盖模式 - 删除原有排班
                Schedule.objects.filter(duty_date=duty_date).delete()
            else:
                raise serializers.ValidationError(
                    {'duty_date': '该日期已有排班'}
                )
        serializer.save()

    def perform_update(self, serializer):
        """更新排班时检查日期是否冲突"""
        duty_date = serializer.validated_data.get('duty_date')
        override = self.request.data.get('override', False)
        
        conflicting_schedules = Schedule.objects.filter(duty_date=duty_date).exclude(pk=serializer.instance.pk)
        if conflicting_schedules.exists():
            if override:
                # 覆盖模式 - 删除冲突的排班
                conflicting_schedules.delete()
            else:
                raise serializers.ValidationError(
                    {'duty_date': '该日期已有排班'}
                )
        serializer.save()

    @action(detail=False, methods=['post'], url_path='swap-dates')
    def swap_dates(self, request):
        """交换两个排班的日期"""
        schedule_id_1 = request.data.get('schedule_id_1')
        schedule_id_2 = request.data.get('schedule_id_2')
        
        if not schedule_id_1 or not schedule_id_2:
            return Response({'error': 'schedule_id_1 and schedule_id_2 are required'}, status=400)
        
        try:
            with transaction.atomic():
                schedule1 = Schedule.objects.get(pk=schedule_id_1)
                schedule2 = Schedule.objects.get(pk=schedule_id_2)
                
                # 交换日期
                temp_date = schedule1.duty_date
                schedule1.duty_date = schedule2.duty_date
                schedule2.duty_date = temp_date
                
                # 保存并验证
                schedule1.save()
                schedule2.save()
                
                return Response({
                    'status': 'success',
                    'schedule1': ScheduleSerializer(schedule1).data,
                    'schedule2': ScheduleSerializer(schedule2).data
                })
        except Schedule.DoesNotExist:
            return Response({'error': 'One or both schedules not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'], url_path='generate-schedules')
    def generate_schedules(self, request):
        """
        根据人员顺序和起始日期自动生成排班。
        请求体示例:
        {
            "start_date": "2025-01-01",
            "personnel_order": [1, 2, 3, 4], // 人员ID列表，按顺序排班
            "duration_days": 30 // 可选，生成排班的天数，默认为30天
        }
        """
        start_date_str = request.data.get('start_date')
        personnel_order = request.data.get('personnel_order')
        duration_days = request.data.get('duration_days', 30)

        if not start_date_str or not personnel_order:
            return Response({'error': 'start_date and personnel_order are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(personnel_order, list) or not all(isinstance(p_id, int) for p_id in personnel_order):
            return Response({'error': 'personnel_order must be a list of integers (personnel IDs).'}, status=status.HTTP_400_BAD_REQUEST)

        if not personnel_order:
            return Response({'error': 'personnel_order cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 验证人员ID是否存在
            personnel_ids = set(personnel_order)
            existing_personnel = Personnel.objects.filter(id__in=personnel_ids)
            if existing_personnel.count() != len(personnel_ids):
                missing_ids = personnel_ids - set(p.id for p in existing_personnel)
                return Response({'error': f'Personnel IDs not found: {list(missing_ids)}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'Error validating personnel: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        created_schedules = []
        with transaction.atomic():
            for i in range(duration_days):
                current_date = start_date + timedelta(days=i)
                
                # 轮流选择值班人员和领导
                # 确保值班人员和值班领导不是同一个人
                duty_person_id = personnel_order[i % len(personnel_order)]
                duty_leader_id = personnel_order[(i + 1) % len(personnel_order)]

                # 确保值班人员和值班领导不同
                if duty_person_id == duty_leader_id:
                    # 如果只有一个人，或者轮到同一个人，则尝试跳过或选择下一个
                    if len(personnel_order) == 1:
                        return Response({'error': 'Cannot assign duty_person and duty_leader to the same person with only one personnel in order.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    # 尝试选择下一个人员作为领导
                    duty_leader_id = personnel_order[(i + 2) % len(personnel_order)]
                    if duty_person_id == duty_leader_id:
                        # 如果仍然相同，说明人员顺序有问题，或者人员太少
                        return Response({'error': 'Cannot assign duty_person and duty_leader to different persons with the given personnel order.'}, status=status.HTTP_400_BAD_REQUEST)

                # 检查该日期是否已有排班，如果有则覆盖
                existing_schedule = Schedule.objects.filter(duty_date=current_date)
                if existing_schedule.exists():
                    existing_schedule.delete() # 删除旧排班

                schedule_data = {
                    'duty_date': current_date,
                    'duty_person': Personnel.objects.get(id=duty_person_id),
                    'duty_leader': Personnel.objects.get(id=duty_leader_id)
                }
                
                schedule = Schedule.objects.create(**schedule_data)
                created_schedules.append(schedule)

        serializer = ScheduleSerializer(created_schedules, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ResponsiblePersonViewSet(viewsets.ModelViewSet):
    queryset = Personnel.objects.all()
    serializer_class = PersonnelSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'department', 'phone']

class TrialViewSet(viewsets.ModelViewSet):
    queryset = Trial.objects.all()
    serializer_class = TrialSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
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
        queryset = super().get_queryset().prefetch_related(
            'equipments',
            'responsible_persons',
            'time_slots'
        )
        return queryset.order_by('-start_date')

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

class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.all().order_by('-created_at')
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

class ImageUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = UploadedImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            image_url = request.build_absolute_uri(serializer.instance.image.url)
            return Response({'url': image_url}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
