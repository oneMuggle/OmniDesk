from datetime import timedelta
from django.utils import timezone
from meeting_rooms.models import MeetingRoom, MeetingRoomBooking
from .base import BaseTool


class MeetingRoomTool(BaseTool):
    name = "meeting_room_query"
    description = "查询会议室可用性和预订"
    intent_type = "meeting_room_query"

    def execute(self, query: str, context: dict | None = None) -> dict:
        """查询会议室可用性和预订信息"""
        target_date = timezone.now().date()

        if "明天" in query:
            target_date = (timezone.now() + timedelta(days=1)).date()
        elif "后天" in query:
            target_date = (timezone.now() + timedelta(days=2)).date()
        elif "昨天" in query:
            target_date = (timezone.now() - timedelta(days=1)).date()
        elif "今天" in query:
            target_date = timezone.now().date()

        # 查询所有会议室
        rooms = MeetingRoom.objects.filter(is_active=True)[:20]

        if not rooms.exists():
            return {
                "found": False,
                "message": "暂无可用的会议室",
            }

        # 查询指定日期的预订
        bookings = MeetingRoomBooking.objects.filter(
            date=target_date,
            status__in=["pending", "confirmed"],
        ).select_related("room", "user")[:20]

        room_status = []
        for room in rooms:
            room_bookings = [
                {
                    "user": b.user.username if b.user else "未知",
                    "start_time": str(b.start_time),
                    "end_time": str(b.end_time),
                    "topic": b.topic or "无主题",
                }
                for b in bookings
                if b.room_id == room.id
            ]
            room_status.append(
                {
                    "name": room.name,
                    "capacity": room.capacity,
                    "floor": room.floor,
                    "is_available": len(room_bookings) == 0,
                    "bookings": room_bookings,
                }
            )

        return {
            "found": True,
            "date": str(target_date),
            "rooms": room_status,
        }
