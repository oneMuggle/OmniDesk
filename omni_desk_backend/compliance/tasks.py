from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import ComplianceIssue

@shared_task
def check_compliance_due_dates():
    """
    Celery 任务：定期扫描 ComplianceIssue，检查到期日期并更新状态。
    """
    print(f"[{timezone.now()}] Running check_compliance_due_dates task...")

    # 查找所有状态不是“已解决”或“已忽略”的合规问题
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
        original_status = issue.status
        
        if issue.due_date and issue.due_date <= today:
            # 如果已过期，将状态更新为“已过期”（如果模型中没有，可以添加）或“待处理”/“紧急”
            if issue.status != '紧急': # 避免重复设置
                issue.status = '紧急' # 假设“紧急”表示已过期或需立即关注
                issue.severity = '紧急' # 提升严重程度
                issue.description += f" (已于 {issue.due_date} 到期，请立即处理！)"
                issue.save()
                updated_count += 1
                print(f"Updated expired issue: {issue.id} - {issue.description}")
        elif issue.due_date and today < issue.due_date <= seven_days_later:
            # 如果即将到期，可以更新状态或添加提醒信息
            if issue.status == '待处理': # 仅对“待处理”状态的进行提示
                issue.status = '处理中' # 表示需要关注
                issue.description += f" (将于 {issue.due_date} 到期，请及时处理！)"
                issue.save()
                updated_count += 1
                print(f"Updated upcoming issue: {issue.id} - {issue.description}")
        
        # 如果需要发送通知，可以在这里调用通知服务
        # 例如：send_notification_to_user(issue.project.manager, f"合规问题提醒：{issue.description}")

    print(f"[{timezone.now()}] check_compliance_due_dates task finished. Updated {updated_count} issues.")
