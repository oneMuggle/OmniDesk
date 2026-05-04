from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from datetime import date, timedelta
from django.utils import timezone


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """聚合仪表盘数据：今日排班、备忘录提醒、最新公告、项目概览、未读通知"""
    user = request.user

    # 今日排班
    from events.models import Schedule
    today_schedules = Schedule.objects.filter(duty_date=date.today()).select_related(
        'duty_person', 'duty_leader'
    )
    today_schedule_list = [
        {
            'duty_person': s.duty_person.name if s.duty_person else None,
            'duty_leader': s.duty_leader.name if s.duty_leader else None,
        }
        for s in today_schedules
    ]

    # 最新公告（最近 5 条）
    from events.models import Announcement
    recent_announcements = Announcement.objects.order_by('-created_at')[:5].values(
        'id', 'title', 'created_at', 'author__username'
    )

    # 备忘录（当前用户的未完成备忘录，7 天内到期）
    from memos.models import Memo
    now = timezone.now()
    memos_due = Memo.objects.filter(
        user=user, is_completed=False, reminder_time__isnull=False,
        reminder_time__lte=now + timedelta(days=7)
    ).order_by('reminder_time')[:5].values('id', 'title', 'reminder_time', 'is_completed')

    # 项目概览
    from projects.models import Project
    active_projects = Project.objects.filter(status='进行中').count()
    recent_projects = Project.objects.order_by('-updated_at')[:5].values(
        'id', 'name', 'status', 'updated_at', 'manager__username'
    )

    # 未读通知
    from notifications.models import Notification
    unread_notifications = Notification.objects.filter(user=user, is_read=False).count()

    return Response({
        'today_schedule': today_schedule_list,
        'recent_announcements': list(recent_announcements),
        'memos_due': list(memos_due),
        'projects': {
            'active_count': active_projects,
            'recent': list(recent_projects),
        },
        'unread_notifications': unread_notifications,
    })
