# DRFForVue/compliance/tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import ComplianceIssue
# from DRFForVue.celery import app # 如果需要直接引用app实例

@shared_task
def check_compliance_due_dates():
    """
    定期检查 ComplianceIssue 模型中 due_date 临近或已过期的项，并更新其状态。
    """
    # 获取今天及未来7天内到期的合规问题
    seven_days_from_now = timezone.now().date() + timedelta(days=7)
    
    # 查找状态为“待处理”且即将到期或已过期的合规问题
    # 假设我们想把即将到期的改为“处理中”，已过期的改为“已忽略”或“过期”
    # 这里我们简化处理，将临近到期的标记为“处理中”，已过期的标记为“已忽略”
    
    # 临近到期的问题 (未来7天内)
    upcoming_issues = ComplianceIssue.objects.filter(
        status='待处理',
        due_date__lte=seven_days_from_now,
        due_date__gte=timezone.now().date()
    )
    for issue in upcoming_issues:
        issue.status = '处理中'
        issue.save()
        print(f"Compliance Issue {issue.id} - '{issue.description}' is upcoming. Status updated to '处理中'.")

    # 已过期的问题
    overdue_issues = ComplianceIssue.objects.filter(
        status='待处理',
        due_date__lt=timezone.now().date()
    )
    for issue in overdue_issues:
        issue.status = '已忽略' # 或者可以定义一个 '已过期' 状态
        issue.save()
        print(f"Compliance Issue {issue.id} - '{issue.description}' is overdue. Status updated to '已忽略'.")

    # 可以在这里添加通知逻辑，例如发送邮件或创建Notification记录
    print("Compliance due date check completed.")

# 可以在 settings.py 中通过 CELERY_BEAT_SCHEDULE 配置此任务的调度
# 例如:
# CELERY_BEAT_SCHEDULE = {
#     'check-compliance-due-dates-every-day': {
#         'task': 'compliance.tasks.check_compliance_due_dates',
#         'schedule': timedelta(days=1), # 每天执行一次
#     },
# }