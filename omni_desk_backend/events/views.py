from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework import viewsets, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from users.permissions import IsAdminOrManager, IsAdminOrManagerOrReadOnly
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
import calendar
from datetime import datetime, timedelta

from django.db.models import Min, Max
from django.db.models.functions import TruncDate

from .models import (
    Trial, TimeSlot, Equipment, DocumentTemplate, Schedule, Announcement, UploadedImage,
    PersonnelSequence, LeaderSequence, Holiday, Position
)
from .serializers import (
    TrialSerializer,
    EquipmentSerializer,
    DocumentTemplateSerializer,
    TimeSlotSerializer,
    ScheduleSerializer,
    AnnouncementSerializer,
    UploadedImageSerializer,
    PersonnelSequenceSerializer,
    LeaderSequenceSerializer,
    HolidaySerializer,
    PositionSerializer
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
    queryset = Schedule.objects.select_related('duty_person', 'duty_leader')
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

    def create(self, request, *args, **kwargs):
        """
        创建排班。
        如果提供了 `override=True`，并且当天已存在排班，则会删除旧排班并创建新排班。
        否则，如果排班已存在，则会引发 ValidationError。
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        duty_date = serializer.validated_data.get('duty_date')
        override = str(request.data.get('override', 'false')).lower() == 'true'

        with transaction.atomic():
            existing_schedule = Schedule.objects.filter(duty_date=duty_date).first()
            
            if existing_schedule:
                if override:
                    existing_schedule.delete()
                else:
                    from rest_framework.exceptions import ValidationError
                    raise ValidationError({'duty_date': '该日期已有排班。如需覆盖，请设置 override=True。'})
            
            serializer.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_update(self, serializer):
        """更新排班时检查日期是否冲突，并确保外键字段正确更新。"""
        duty_date = serializer.validated_data.get('duty_date', serializer.instance.duty_date)
        
        # 检查日期冲突
        if Schedule.objects.filter(duty_date=duty_date).exclude(pk=serializer.instance.pk).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'duty_date': '该日期已有排班'})
        
        # 显式传递 duty_person_id 和 duty_leader_id 以确保更新
        # 这是为了解决测试中发现的 PUT 请求未更新这些字段的问题
        update_kwargs = {}
        if 'duty_person_id' in self.request.data:
            update_kwargs['duty_person_id'] = self.request.data.get('duty_person_id')
        if 'duty_leader_id' in self.request.data:
            update_kwargs['duty_leader_id'] = self.request.data.get('duty_leader_id')

        serializer.save(**update_kwargs)

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

    @action(detail=False, methods=['post'], url_path='swap-weekly-leaders')
    def swap_weekly_leaders(self, request):
        """
        交换两周的值班领导。
        接收 source_week_start_date 和 destination_week_start_date。
        """
        source_week_start_date_str = request.data.get('source_week_start_date')
        destination_week_start_date_str = request.data.get('destination_week_start_date')

        if not source_week_start_date_str or not destination_week_start_date_str:
            return Response({'error': 'Both source and destination week start dates are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            source_start = datetime.strptime(source_week_start_date_str, '%Y-%m-%d').date()
            destination_start = datetime.strptime(destination_week_start_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        source_end = source_start + timedelta(days=6)
        destination_end = destination_start + timedelta(days=6)

        with transaction.atomic():
            source_schedules = list(Schedule.objects.filter(duty_date__range=[source_start, source_end]))
            destination_schedules = list(Schedule.objects.filter(duty_date__range=[destination_start, destination_end]))

            if not source_schedules and not destination_schedules:
                return Response({'status': 'success', 'message': 'No schedules to swap in the given weeks.'})

            source_leader = source_schedules[0].duty_leader if source_schedules else None
            destination_leader = destination_schedules[0].duty_leader if destination_schedules else None

            # Swap leaders
            for schedule in source_schedules:
                schedule.duty_leader = destination_leader
                schedule.save()

            for schedule in destination_schedules:
                schedule.duty_leader = source_leader
                schedule.save()

        return Response({'status': 'success'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='generate-schedules')
    def generate_schedules(self, request):
        """
        根据人员顺序、起始日期或月份自动生成排班。
        支持指定起始人员和领导。
        区分工作日和节假日进行排班。
        """
        personnel_sequence_id = request.data.get('personnel_sequence_id')
        leader_sequence_id = request.data.get('leader_sequence_id')
        start_personnel_id = request.data.get('start_personnel_id')
        start_leader_id = request.data.get('start_leader_id')
        target_month = request.data.get('target_month')  # e.g., "2025-09"
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

        workday_personnel_order = personnel_sequence.sequence
        # 如果节假日序列未配置，则使用工作日序列
        holiday_personnel_order = personnel_sequence.holiday_sequence if personnel_sequence.holiday_sequence else workday_personnel_order
        leader_order = leader_sequence.sequence

        if not workday_personnel_order or not leader_order:
            return Response({'error': 'Sequence cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        # 获取时间范围内的所有节假日
        end_date = start_date + timedelta(days=duration_days - 1)
        holidays = Holiday.objects.filter(start_date__lte=end_date, end_date__gte=start_date)
        holiday_dates = set()
        for holiday in holidays:
            current_day = holiday.start_date
            while current_day <= holiday.end_date:
                if start_date <= current_day <= end_date:
                    holiday_dates.add(current_day)
                current_day += timedelta(days=1)

        workday_start_index = 0
        holiday_start_index = 0
        is_start_day_holiday = start_date in holiday_dates

        if start_personnel_id:
            try:
                start_personnel_id_int = int(start_personnel_id)
                if is_start_day_holiday:
                    holiday_start_index = holiday_personnel_order.index(start_personnel_id_int)
                else:
                    workday_start_index = workday_personnel_order.index(start_personnel_id_int)
            except (ValueError, TypeError):
                return Response({'error': f'start_personnel_id {start_personnel_id} not in the corresponding sequence.'}, status=status.HTTP_400_BAD_REQUEST)

        leader_start_index = 0
        if start_leader_id:
            try:
                leader_start_index = leader_order.index(int(start_leader_id))
            except (ValueError, TypeError):
                return Response({'error': f'start_leader_id {start_leader_id} not in sequence.'}, status=status.HTTP_400_BAD_REQUEST)

        created_schedules = []
        with transaction.atomic():
            workday_count = 0
            holiday_count = 0
            
            for i in range(duration_days):
                current_date = start_date + timedelta(days=i)
                is_holiday = current_date in holiday_dates

                if is_holiday:
                    if not holiday_personnel_order:
                        return Response({'error': 'Holiday sequence is not configured and fallback is not available.'}, status=status.HTTP_400_BAD_REQUEST)
                    personnel_idx = (holiday_start_index + holiday_count) % len(holiday_personnel_order)
                    duty_person_id = holiday_personnel_order[personnel_idx]
                    holiday_count += 1
                else:
                    personnel_idx = (workday_start_index + workday_count) % len(workday_personnel_order)
                    duty_person_id = workday_personnel_order[personnel_idx]
                    workday_count += 1
                
                # Weekly rotation for leaders remains unchanged
                weeks_passed = (current_date - start_date).days // 7
                leader_idx = (leader_start_index + weeks_passed) % len(leader_order)
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

    @action(detail=False, methods=['post'], url_path='bulk_destroy')
    def bulk_delete(self, request):
        """
        批量删除排班记录。
        接收一个包含排班 ID 列表的 POST 请求。
        请求体格式: { "ids": [1, 2, 3] }
        """
        schedule_ids = request.data.get('ids', [])

        if not isinstance(schedule_ids, list):
            return Response(
                {'error': 'Invalid data format. "ids" should be a list.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                Schedule.objects.filter(pk__in=schedule_ids).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {'error': 'An internal server error occurred.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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


class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['date']

    def get_queryset(self):
        """
        Optionally restricts the returned holidays to a given year,
        by filtering against a `year` query parameter in the URL.
        """
        queryset = Holiday.objects.all()
        year = self.request.query_params.get('year')
        if year is not None:
            queryset = queryset.filter(date__year=year)
        return queryset

class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'start_date', 'end_date']


class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [permissions.IsAuthenticated]
