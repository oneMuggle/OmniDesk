from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import ComplianceIssue


@shared_task
def check_compliance_due_dates():
    """
    Celery 任务：定期扫描 ComplianceIssue，检查到期日期并更新状态。
    """
    print(f"[{timezone.now()}] Running check_compliance_due_dates task...")

    # 查找所有状态不是"已解决"或"已忽略"的合规问题
    # 并且其 due_date 小于或等于今天
    # 或者 due_date 在未来 7 天内（作为即将到期的提醒）

    # 获取今天日期
    today = timezone.localdate()
    # 计算 7 天后的日期
    seven_days_later = today + timedelta(days=7)

    # 查找即将到期和已到期的 ComplianceIssue
    issues_to_check = ComplianceIssue.objects.filter(
        status__in=['待处理', '处理中']
    ).filter(
        due_date__lte=seven_days_later # 包括今天和未来的7天内到期的，以及所有已过期的
    )

    updated_count = 0
    for issue in issues_to_check:
        if issue.due_date and issue.due_date <= today:
            if issue.status != '紧急':
                issue.status = '紧急'
                issue.severity = '紧急'
                issue.save()
                updated_count += 1
                print(f"Updated expired issue: {issue.id} - {issue.description}")
        elif issue.due_date and today < issue.due_date <= seven_days_later:
            if issue.status == '待处理':
                issue.status = '处理中'
                issue.save()
                updated_count += 1
                print(f"Updated upcoming issue: {issue.id} - {issue.description}")

        # 如果需要发送通知，可以在这里调用通知服务
        # 例如：send_notification_to_user(issue.project.manager, f"合规问题提醒：{issue.description}")

    print(f"[{timezone.now()}] check_compliance_due_dates task finished. Updated {updated_count} issues.")
