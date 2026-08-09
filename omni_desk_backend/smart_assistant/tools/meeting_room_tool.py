from datetime import datetime, time, timedelta
from django.utils import timezone
from meeting_rooms.models import MeetingRoom, MeetingRoomBooking
from .base import BaseTool


class MeetingRoomTool(BaseTool):
    name = "meeting_room_query"
    description = "查询会议室可用性和预订"
    intent_type = "meeting_room_query"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """查询会议室(支持新旧两种签名)"""
        target_date = timezone.now().date()
        date_text = query or ""
        if isinstance(params, dict) and params.get("target_date"):
            date_text = str(params["target_date"])
        if "明天" in date_text:
            target_date = (timezone.now() + timedelta(days=1)).date()
        elif "后天" in date_text:
            target_date = (timezone.now() + timedelta(days=2)).date()
        elif "昨天" in date_text:
            target_date = (timezone.now() - timedelta(days=1)).date()
        elif "今天" in date_text:
            target_date = timezone.now().date()
        elif isinstance(params, dict) and params.get("target_date"):
            # I-2:结构化 target_date(ISO 8601 日期)直接作为目标日期
            from datetime import date as _date

            try:
                target_date = _date.fromisoformat(str(params["target_date"])[:10])
            except ValueError:
                pass  # 非法日期保持默认今天

        if qs is None:
            qs = MeetingRoom.objects.all()
        rooms = qs[:20]

        if not rooms.exists():
            return {"found": False, "message": "暂无可用的会议室", "module_label": "会议室"}

        day_start = timezone.make_aware(datetime.combine(target_date, time.min))
        day_end = timezone.make_aware(datetime.combine(target_date, time.max))
        bookings = MeetingRoomBooking.objects.filter(
            start_time__gte=day_start,
            start_time__lte=day_end,
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
            room_status.append(
                {
                    "name": room.name,
                    "capacity": room.capacity,
                    "floor": room.location or "未指定",
                    "is_available": len(room_bookings) == 0,
                    "bookings": room_bookings,
                }
            )

        return {
            "found": True,
            "date": str(target_date),
            "rooms": room_status,
            "module_label": "会议室",
        }

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 查询会议室可用性。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询会议室可用性与预订情况,按日期聚合。"
                    "示例 query: '明天的会议室有空吗'、'今天 3 楼会议室预订'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言查询,可含日期/楼层关键词",
                        },
                        "target_date": {
                            "type": "string",
                            "format": "date",
                            "description": "目标日期(ISO 8601),不传则默认今天",
                        },
                        "capacity_min": {
                            "type": "integer",
                            "description": "最少容纳人数(可选)",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def build_base_queryset(self):
        from meeting_rooms.models import MeetingRoom

        return MeetingRoom.objects.all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 有过预订的会议室。"""
        from meeting_rooms.models import MeetingRoomBooking

        user_room_ids = MeetingRoomBooking.objects.filter(user=ctx.user).values_list("meeting_room_id", flat=True)
        return qs.filter(id__in=user_room_ids).distinct()
