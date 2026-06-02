from datetime import timedelta
from django.utils import timezone
from events.models import Schedule
from .base import BaseTool


class ScheduleTool(BaseTool):
    name = "schedule_query"
    description = "查询排班、值班安排"
    intent_type = "schedule_query"

    def execute(self, query: str, context: dict = None) -> dict:
        """解析自然语言中的日期，查询排班信息"""
        target_date = timezone.now().date()

        if "明天" in query:
            target_date = (timezone.now() + timedelta(days=1)).date()
        elif "后天" in query:
            target_date = (timezone.now() + timedelta(days=2)).date()
        elif "昨天" in query:
            target_date = (timezone.now() - timedelta(days=1)).date()

        schedules = Schedule.objects.filter(duty_date=target_date).select_related("duty_person", "duty_leader")

        if not schedules.exists():
            return {
                "date": str(target_date),
                "found": False,
                "message": f"{target_date} 暂无排班记录",
            }

        results = []
        for s in schedules:
            results.append(
                {
                    "duty_date": str(s.duty_date),
                    "duty_person": s.duty_person.name if s.duty_person else "未安排",
                    "duty_leader": s.duty_leader.name if s.duty_leader else "未安排",
                }
            )

        return {
            "date": str(target_date),
            "found": True,
            "schedules": results,
        }

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "intent_type": self.intent_type,
        }
