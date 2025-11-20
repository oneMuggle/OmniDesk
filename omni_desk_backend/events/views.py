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
import calendar
from datetime import datetime, timedelta

from django.db.models import Min, Max
from django.db.models.functions import TruncDate

from .models import (
    Trial, TimeSlot, Personnel, Equipment, DocumentTemplate, Schedule, Announcement, UploadedImage,
    PersonnelSequence, LeaderSequence, Position, PhoneNumber
)
from .serializers import (
    TrialSerializer,
    PersonnelSerializer,
    EquipmentSerializer,
    DocumentTemplateSerializer,
    TimeSlotSerializer,
    ScheduleSerializer,
    AnnouncementSerializer,
    UploadedImageSerializer,
    PersonnelSequenceSerializer,
    LeaderSequenceSerializer,
    PositionSerializer
)
from django_filters.rest_framework import DjangoFilterBackend

class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [IsAdminOrManager] # 只有管理员和经理可以管理职位
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name']

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
    queryset = Schedule.objects.select_related('duty_person', 'duty_leader').prefetch_related('duty_person__phone_numbers', 'duty_leader__phone_numbers')
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
                
                # 交换人员和领导，而不是日期，以避免违反UNIQUE约束
                temp_person = schedule1.duty_person
                temp_leader = schedule1.duty_leader

                schedule1.duty_person = schedule2.duty_person
                schedule1.duty_leader = schedule2.duty_leader

                schedule2.duty_person = temp_person
                schedule2.duty_leader = temp_leader
                
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
        根据人员顺序、起始日期或月份自动生成排班。
        支持指定起始人员和领导。
        """
        personnel_sequence_id = request.data.get('personnel_sequence_id')
        leader_sequence_id = request.data.get('leader_sequence_id')
        start_personnel_id = request.data.get('start_personnel_id')
        start_leader_id = request.data.get('start_leader_id')
        target_month = request.data.get('target_month') # e.g., "2025-09"
        duration_days = request.data.get('duration_days')
        start_date_str = request.data.get('start_date')

        if not personnel_sequence_id or not leader_sequence_id:
            return Response({'error': 'personnel_sequence_id and leader_sequence_id are required'}, status=status.HTTP_400_BAD_REQUEST)

        if target_month:
            try:
                month_date = datetime.strptime(target_month, '%Y-%m').date()
                start_date = month_date.replace(day=1)
                _, num_days = calendar.monthrange(start_date.year, start_date.month)
                duration_days = num_days
            except ValueError:
                return Response({'error': 'Invalid month format. Use YYYY-MM.'}, status=status.HTTP_400_BAD_REQUEST)
        elif duration_days and start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                duration_days = int(duration_days)
            except (ValueError, TypeError):
                return Response({'error': 'Invalid date or duration format.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'error': 'Either target_month or both start_date and duration_days are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            personnel_sequence = PersonnelSequence.objects.get(id=personnel_sequence_id)
            leader_sequence = LeaderSequence.objects.get(id=leader_sequence_id)
        except (PersonnelSequence.DoesNotExist, LeaderSequence.DoesNotExist):
            return Response({'error': 'Invalid sequence ID'}, status=status.HTTP_404_NOT_FOUND)

        personnel_order = personnel_sequence.sequence
        leader_order = leader_sequence.sequence

        if not personnel_order or not leader_order:
            return Response({'error': 'Sequence cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        personnel_start_index = 0
        if start_personnel_id:
            try:
                personnel_start_index = personnel_order.index(int(start_personnel_id))
            except (ValueError, TypeError):
                return Response({'error': f'start_personnel_id {start_personnel_id} not in sequence.'}, status=status.HTTP_400_BAD_REQUEST)

        leader_start_index = 0
        if start_leader_id:
            try:
                leader_start_index = leader_order.index(int(start_leader_id))
            except (ValueError, TypeError):
                return Response({'error': f'start_leader_id {start_leader_id} not in sequence.'}, status=status.HTTP_400_BAD_REQUEST)

        created_schedules = []
        with transaction.atomic():
            for i in range(duration_days):
                current_date = start_date + timedelta(days=i)
                
                personnel_idx = (personnel_start_index + i) % len(personnel_order)
                leader_idx = (leader_start_index + i) % len(leader_order)
                
                duty_person_id = personnel_order[personnel_idx]
                duty_leader_id = leader_order[leader_idx]

                Schedule.objects.filter(duty_date=current_date).delete()

                schedule_data = {
                    'duty_date': current_date,
                    'duty_person_id': duty_person_id,
                    'duty_leader_id': duty_leader_id
                }
                
                schedule = Schedule.objects.create(**schedule_data)
                created_schedules.append(schedule)

        serializer = ScheduleSerializer(created_schedules, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

from rest_framework.filters import SearchFilter

class PersonnelViewSet(viewsets.ModelViewSet):
    queryset = Personnel.objects.all().prefetch_related('phone_numbers')
    serializer_class = PersonnelSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['position']
    search_fields = ['name']

    @action(detail=False, methods=['get'], url_path='all')
    def list_all(self, request):
        """
        获取所有人员信息，不进行分页。
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        phone_numbers_data = self.request.data.get('phone_numbers', [])
        with transaction.atomic():
            personnel = serializer.save()
            for phone_data in phone_numbers_data:
                PhoneNumber.objects.create(personnel=personnel, **phone_data)

    def perform_update(self, serializer):
        phone_numbers_data = self.request.data.get('phone_numbers', None)
        with transaction.atomic():
            personnel = serializer.save()
            if phone_numbers_data is not None:
                # 删除旧的电话号码
                personnel.phone_numbers.all().delete()
                # 创建新的电话号码
                for phone_data in phone_numbers_data:
                    PhoneNumber.objects.create(personnel=personnel, **phone_data)

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

    @action(detail=False, methods=['get'], url_path='this-week')
    def get_this_week_trials(self, request):
        """
        获取本周的试验日程。
        """
        today = timezone.now().date()
        # 计算本周的开始日期 (周一)
        start_of_week = today - timedelta(days=today.weekday())
        # 计算本周的结束日期 (周日)
        end_of_week = start_of_week + timedelta(days=6)

        # 过滤本周的试验，考虑试验的主时间范围 (start_date, end_date) 与本周的重叠
        # 或者考虑试验的时间段 (time_slots) 与本周的重叠
        queryset = self.get_queryset().filter(
            # 试验的主时间范围与本周有交集
            # (start_date <= end_of_week AND end_date >= start_of_week)
            start_date__lte=end_of_week,
            end_date__gte=start_of_week
        ).distinct() # 使用 distinct 避免重复，因为 time_slots 是多对多

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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
        # 乐观锁检查
        # 乐观锁检查
        current_version = serializer.instance.version
        if 'version' in self.request.data:
            if self.request.data['version'] != current_version:
                raise serializers.ValidationError(
                    {'version': '数据已被其他用户修改，请刷新后重试'}
                )
        
        # 更新试验基本信息并增加版本号
        serializer.save(version=current_version + 1)
        # 关联关系的更新由serializer的update方法处理
        # 时间段的增删改由serializer的update方法处理

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
            trial.update_time_range()
        
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
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PersonnelSequenceViewSet(viewsets.ModelViewSet):
    """
    人员顺序视图集
    """
    queryset = PersonnelSequence.objects.all()
    serializer_class = PersonnelSequenceSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]

class LeaderSequenceViewSet(viewsets.ModelViewSet):
    """
    领导顺序视图集
    """
    queryset = LeaderSequence.objects.all()
    serializer_class = LeaderSequenceSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
