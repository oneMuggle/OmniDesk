"""events.views.schedules — 排班相关 ViewSet

拆分自原 events/views.py(Phase 3 优化)。包含:
- ScheduleViewSet: 排班 CRUD + 自动生成 + 批量操作 + 日期交换
- MyScheduleView: 当前用户未来 N 天值班自助查询
"""

import calendar
import logging
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.permissions import IsAdminOrManagerOrReadOnly

from ..models import LeaderSequence, PersonnelSequence, Schedule
from ..schedule_generator import ScheduleGenerator
from ..serializers import GenerateScheduleSerializer, ScheduleSerializer

logger = logging.getLogger(__name__)


class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.select_related("duty_person", "duty_leader")
    serializer_class = ScheduleSerializer

    @action(detail=False, methods=["post"])
    def upsert(self, request):
        """创建或更新排班记录"""
        data = request.data
        if data.get("id"):
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=data, partial=True)
        else:
            serializer = self.get_serializer(data=data)

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    permission_classes = [IsAdminOrManagerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["duty_date", "duty_person", "duty_leader"]
    ordering_fields = ["duty_date"]

    @action(detail=False, methods=["get"], url_path="by-date-range")
    def by_date_range(self, request):
        """按日期范围查询排班"""
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if not start_date or not end_date:
            return Response({"error": "start_date and end_date are required"}, status=400)

        queryset = self.queryset.filter(duty_date__gte=start_date, duty_date__lte=end_date).order_by("duty_date")

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="bulk-update")
    def bulk_update(self, request):
        """批量更新排班"""
        schedules_data = request.data.get("schedules", [])

        with transaction.atomic():
            if request.data.get("clear_existing", False):
                Schedule.objects.all().delete()

            new_schedules = []
            for schedule_data in schedules_data:
                serializer = self.get_serializer(data=schedule_data)
                serializer.is_valid(raise_exception=True)
                new_schedules.append(Schedule(**serializer.validated_data))

            Schedule.objects.bulk_create(new_schedules)

        return Response({"status": "success"}, status=201)

    def create(self, request, *args, **kwargs):
        """创建排班。支持 override=True 覆盖已有排班。"""
        override = str(request.data.get("override", "false")).lower() == "true"
        duty_date_str = request.data.get("duty_date")

        with transaction.atomic():
            try:
                duty_date = datetime.strptime(duty_date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                duty_date = None

            if duty_date:
                existing_schedule = Schedule.objects.filter(duty_date=duty_date).first()
                if existing_schedule:
                    if override:
                        existing_schedule.delete()
                    else:
                        from rest_framework.exceptions import ValidationError

                        raise ValidationError({"duty_date": "该日期已有排班。如需覆盖，请设置 override=True。"})

            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            save_kwargs = {}
            duty_person_val = request.data.get("duty_person_id") or request.data.get("duty_person")
            if duty_person_val:
                save_kwargs["duty_person_id"] = duty_person_val

            duty_leader_val = request.data.get("duty_leader_id") or request.data.get("duty_leader")
            if duty_leader_val:
                save_kwargs["duty_leader_id"] = duty_leader_val

            serializer.save(**save_kwargs)

            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_update(self, serializer):
        """更新排班时检查日期冲突，并确保外键字段正确更新。"""
        duty_date = serializer.validated_data.get("duty_date", serializer.instance.duty_date)

        if Schedule.objects.filter(duty_date=duty_date).exclude(pk=serializer.instance.pk).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"duty_date": "该日期已有排班"})

        update_kwargs = {}
        if "duty_person_id" in self.request.data:
            update_kwargs["duty_person_id"] = self.request.data.get("duty_person_id")
        if "duty_leader_id" in self.request.data:
            update_kwargs["duty_leader_id"] = self.request.data.get("duty_leader_id")

        serializer.save(**update_kwargs)

    @action(detail=False, methods=["post"], url_path="swap-dates")
    def swap_dates(self, request):
        """交换两个排班的日期"""
        schedule_id_1 = request.data.get("schedule_id_1")
        schedule_id_2 = request.data.get("schedule_id_2")

        if not schedule_id_1 or not schedule_id_2:
            return Response({"error": "schedule_id_1 and schedule_id_2 are required"}, status=400)

        try:
            with transaction.atomic():
                schedule1 = Schedule.objects.get(pk=schedule_id_1)
                schedule2 = Schedule.objects.get(pk=schedule_id_2)

                temp_person = schedule1.duty_person
                temp_leader = schedule1.duty_leader

                schedule1.duty_person = schedule2.duty_person
                schedule1.duty_leader = schedule2.duty_leader

                schedule2.duty_person = temp_person
                schedule2.duty_leader = temp_leader

                schedule1.save()
                schedule2.save()

                return Response(
                    {
                        "status": "success",
                        "schedule1": ScheduleSerializer(schedule1).data,
                        "schedule2": ScheduleSerializer(schedule2).data,
                    }
                )
        except Schedule.DoesNotExist:
            return Response({"error": "One or both schedules not found"}, status=404)

    @action(detail=False, methods=["post"], url_path="swap-weekly-leaders")
    def swap_weekly_leaders(self, request):
        """交换两周的值班领导。"""
        source_week_start_date_str = request.data.get("source_week_start_date")
        destination_week_start_date_str = request.data.get("destination_week_start_date")

        if not source_week_start_date_str or not destination_week_start_date_str:
            return Response(
                {"error": "Both source and destination week start dates are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            source_start = datetime.strptime(source_week_start_date_str, "%Y-%m-%d").date()
            destination_start = datetime.strptime(destination_week_start_date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        source_end = source_start + timedelta(days=6)
        destination_end = destination_start + timedelta(days=6)

        with transaction.atomic():
            source_schedules = list(Schedule.objects.filter(duty_date__range=[source_start, source_end]))
            destination_schedules = list(Schedule.objects.filter(duty_date__range=[destination_start, destination_end]))

            if not source_schedules and not destination_schedules:
                return Response({"status": "success", "message": "No schedules to swap in the given weeks."})

            source_leader = source_schedules[0].duty_leader if source_schedules else None
            destination_leader = destination_schedules[0].duty_leader if destination_schedules else None

            for schedule in source_schedules:
                schedule.duty_leader = destination_leader

            for schedule in destination_schedules:
                schedule.duty_leader = source_leader

            # 批量更新替代循环 save(),修复 N+1
            all_schedules = source_schedules + destination_schedules
            Schedule.objects.bulk_update(all_schedules, ["duty_leader"])

        return Response({"status": "success"}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="generate-schedules")
    def generate_schedules(self, request):
        """根据人员顺序、起始日期或月份自动生成排班。"""
        serializer = GenerateScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        start_date = validated_data.get("start_date")
        target_month = validated_data.get("target_month")
        duration_days = validated_data.get("duration_days")

        if target_month:
            try:
                month_date = datetime.strptime(target_month, "%Y-%m").date()
                start_date = month_date.replace(day=1)
                _, duration_days = calendar.monthrange(start_date.year, start_date.month)
            except ValueError:
                return Response({"error": "Invalid month format. Use YYYY-MM."}, status=status.HTTP_400_BAD_REQUEST)

        workday_sequence = PersonnelSequence.objects.get(id=validated_data["workday_personnel_sequence_id"])
        holiday_sequence = None
        if validated_data.get("holiday_personnel_sequence_id"):
            holiday_sequence = PersonnelSequence.objects.get(id=validated_data["holiday_personnel_sequence_id"])
        leader_sequence = LeaderSequence.objects.get(id=validated_data["leader_sequence_id"])

        with transaction.atomic():
            generated_schedules, _, _ = ScheduleGenerator(
                workday_sequence=workday_sequence,
                leader_sequence=leader_sequence,
                start_date=start_date,
                duration_days=duration_days,
                holiday_sequence=holiday_sequence,
                start_personnel_id=validated_data.get("start_personnel_id"),
                start_holiday_personnel_id=validated_data.get("start_holiday_personnel_id"),
                start_leader_id=validated_data.get("start_leader_id"),
            ).generate()

        return Response(ScheduleSerializer(generated_schedules, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="bulk_destroy")
    def bulk_delete(self, request):
        """批量删除排班记录。"""
        schedule_ids = request.data.get("ids", [])

        if not isinstance(schedule_ids, list):
            return Response(
                {"error": 'Invalid data format. "ids" should be a list.'}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                Schedule.objects.filter(pk__in=schedule_ids).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception:
            logger.exception("批量删除排班失败")
            return Response(
                {"error": "An internal server error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MyScheduleView(generics.ListAPIView):
    """当前登录用户的未来 N 天值班自助查询(/api/events/me/schedule/)。"""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.ModelSerializer

    def get_queryset(self):
        from ..models import Schedule as _Schedule

        personnel = getattr(self.request.user, "personnel", None)
        if personnel is None:
            return _Schedule.objects.none()
        try:
            days = int(self.request.query_params.get("days", 60))
        except (TypeError, ValueError):
            days = 60
        days = max(1, min(days, 365))
        today = timezone.now().date()
        return (
            _Schedule.objects.filter(
                Q(duty_person=personnel) | Q(duty_leader=personnel),
                duty_date__gte=today,
                duty_date__lte=today + timedelta(days=days),
            )
            .select_related("duty_person", "duty_leader")
            .order_by("duty_date")
        )

    def get_serializer_class(self):
        from ..serializers import ScheduleSerializer

        return ScheduleSerializer
