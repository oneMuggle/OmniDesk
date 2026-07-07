from datetime import datetime, time, timedelta
from django.utils import timezone
from meeting_rooms.models import MeetingRoom, MeetingRoomBooking
from .base import BaseTool


class MeetingRoomTool(BaseTool):
    name = "meeting_room_query"
    description = "查询会议室可用性和预订"
    intent_type = "meeting_room_query"

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """查询会议室(支持新旧两种签名)"""
        target_date = timezone.now().date()
        if query:
            if "明天" in query:
                target_date = (timezone.now() + timedelta(days=1)).date()
            elif "后天" in query:
                target_date = (timezone.now() + timedelta(days=2)).date()
            elif "昨天" in query:
                target_date = (timezone.now() - timedelta(days=1)).date()
            elif "今天" in query:
                target_date = timezone.now().date()

        if qs is None:
            qs = MeetingRoom.objects.all()
        rooms = qs[:20]

        if not rooms.exists():
            return {"found": False, "message": "暂无可用的会议室", "module_label": "会议室"}

        day_start = timezone.make_aware(datetime.combine(target_date, time.min))
        day_end = timezone.make_aware(datetime.combine(target_date, time.max))
        bookings = MeetingRoomBooking.objects.filter(
            start_time__gte=day_start, start_time__lte=day_end,
        ).select_related("meeting_room", "user")[:50]

        room_status = []
        for room in rooms:
            room_bookings = [
                {
                    "user": b.user.username if b.user else "未知",
                    "start_time": str(b.start_time),
                    "end_time": str(b.end_time),
                    "topic": b.title or "无主题",
                }
                for b in bookings
                if b.meeting_room_id == room.id
            ]
            room_status.append({
                "name": room.name,
                "capacity": room.capacity,
                "floor": room.location or "未指定",
                "is_available": len(room_bookings) == 0,
                "bookings": room_bookings,
            })

        return {
            "found": True,
            "date": str(target_date),
            "rooms": room_status,
            "module_label": "会议室",
        }

    def build_base_queryset(self):
        from meeting_rooms.models import MeetingRoom
        return MeetingRoom.objects.all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 有过预订的会议室。"""
        from meeting_rooms.models import MeetingRoomBooking
        user_room_ids = MeetingRoomBooking.objects.filter(
            user=ctx.user
        ).values_list("meeting_room_id", flat=True)
        return qs.filter(id__in=user_room_ids).distinct()
