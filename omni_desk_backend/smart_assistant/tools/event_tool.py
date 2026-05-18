from datetime import timedelta
from django.utils import timezone
from events.models import Schedule, Holiday
from .base import BaseTool


class EventTool(BaseTool):
    name = "event_query"
    description = "查询事件/日程/排班/节假日"
    intent_type = "event_query"

    def execute(self, query: str, context: dict = None) -> dict:
        """查询事件和日程信息"""
        target_date = timezone.now().date()

        if "明天" in query:
            target_date = (timezone.now() + timedelta(days=1)).date()
        elif "后天" in query:
            target_date = (timezone.now() + timedelta(days=2)).date()
        elif "昨天" in query:
            target_date = (timezone.now() - timedelta(days=1)).date()
        elif "今天" in query:
            target_date = timezone.now().date()

        schedules = Schedule.objects.filter(duty_date=target_date).select_related(
            'duty_person', 'duty_leader'
        )

        holidays = Holiday.objects.filter(
            start_date__lte=target_date,
            end_date__gte=target_date,
        )

        if not schedules.exists() and not holidays.exists():
            return {
                'found': False,
                'date': str(target_date),
                'message': f'{target_date} 暂无排班或节假日记录',
            }

        results = {
            'date': str(target_date),
            'schedules': [],
            'holidays': [],
        }

        for s in schedules:
            results['schedules'].append({
                'duty_date': str(s.duty_date),
                'duty_person': s.duty_person.name if s.duty_person else '未安排',
                'duty_leader': s.duty_leader.name if s.duty_leader else '未安排',
            })

        for h in holidays:
            results['holidays'].append({
                'name': h.name,
                'start_date': str(h.start_date),
                'end_date': str(h.end_date),
            })

        return {
            'found': True,
            **results,
        }
