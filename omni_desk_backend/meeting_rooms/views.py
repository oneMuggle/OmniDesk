from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Sum, F, ExpressionWrapper, fields
from django.utils import timezone
from datetime import timedelta

from .models import MeetingRoom, MeetingRoomBooking, MeetingRoomMaintenance
from .serializers import MeetingRoomSerializer, MeetingRoomBookingSerializer, MeetingRoomMaintenanceSerializer
from users.permissions import IsAdminOrManager # 假设users应用中有IsAdminOrManager权限类

class MeetingRoomViewSet(viewsets.ModelViewSet):
    queryset = MeetingRoom.objects.all()
    serializer_class = MeetingRoomSerializer
    permission_classes = [IsAdminOrManager] # 只有管理员和经理可以管理会议室

class MeetingRoomBookingViewSet(viewsets.ModelViewSet):
    serializer_class = MeetingRoomBookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and (user.role == 'admin' or user.role == 'manager'):
            return MeetingRoomBooking.objects.all().order_by('start_time')
        return MeetingRoomBooking.objects.filter(user=user).order_by('start_time')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

class MeetingRoomMaintenanceViewSet(viewsets.ModelViewSet):
    queryset = MeetingRoomMaintenance.objects.all().order_by('start_time')
    serializer_class = MeetingRoomMaintenanceSerializer
    permission_classes = [IsAdminOrManager] # 只有管理员和经理可以管理维护时间

class MeetingRoomStatsAPIView(APIView):
    permission_classes = [IsAdminOrManager] # 只有管理员和经理可以访问统计报告

    def get(self, request, *args, **kwargs):
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        meeting_room_id = request.query_params.get('meeting_room_id')

        # 默认时间范围为最近30天
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)

        if start_date_str:
            try:
                start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid start_date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if end_date_str:
            try:
                end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid end_date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        bookings = MeetingRoomBooking.objects.filter(
            start_time__date__gte=start_date,
            end_time__date__lte=end_date
        )

        if meeting_room_id:
            try:
                bookings = bookings.filter(meeting_room_id=int(meeting_room_id))
            except ValueError:
                return Response({"error": "Invalid meeting_room_id."}, status=status.HTTP_400_BAD_REQUEST)

        # 计算总预约时长 (分钟)
        total_booking_duration_minutes = bookings.annotate(
            duration=ExpressionWrapper(
                F('end_time') - F('start_time'),
                output_field=fields.DurationField()
            )
        ).aggregate(total_duration=Sum('duration'))['total_duration']

        total_booking_minutes = total_booking_duration_minutes.total_seconds() / 60 if total_booking_duration_minutes else 0

        # 按会议室统计
        room_stats = bookings.values('meeting_room__name').annotate(
            booking_count=models.Count('id'),
            total_duration_minutes=Sum(
                ExpressionWrapper(
                    F('end_time') - F('start_time'),
                    output_field=fields.DurationField()
                )
            )
        ).order_by('meeting_room__name')

        # 格式化room_stats
        formatted_room_stats = []
        for stat in room_stats:
            duration_seconds = stat['total_duration_minutes'].total_seconds() if stat['total_duration_minutes'] else 0
            formatted_room_stats.append({
                "meeting_room_name": stat['meeting_room__name'],
                "booking_count": stat['booking_count'],
                "total_duration_minutes": duration_seconds / 60
            })

        response_data = {
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": end_date.strftime('%Y-%m-%d'),
            "total_bookings": bookings.count(),
            "total_booking_duration_minutes": total_booking_minutes,
            "room_stats": formatted_room_stats
        }

        return Response(response_data, status=status.HTTP_200_OK)
