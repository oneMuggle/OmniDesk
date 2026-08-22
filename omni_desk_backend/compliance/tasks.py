from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from observability import get_logger
from notifications.models import Notification

from .models import ComplianceIssue

logger = get_logger(__name__, "compliance.tasks")


@shared_task
def check_compliance_due_dates():
    """
    Celery 任务：定期扫描 ComplianceIssue，检查到期日期并更新状态。
    """
    logger.info("Running check_compliance_due_dates task...")

    # 查找所有状态不是"已解决"或"已忽略"的合规问题
    # 并且其 due_date 小于或等于今天
    # 或者 due_date 在未来 7 天内（作为即将到期的提醒）

    # 获取今天日期
    today = timezone.localdate()
    # 计算 7 天后的日期
    seven_days_later = today + timedelta(days=7)

    # 查找即将到期和已到期的 ComplianceIssue
    issues_to_check = ComplianceIssue.objects.filter(status__in=["待处理", "处理中"]).filter(
        due_date__lte=seven_days_later  # 包括今天和未来的7天内到期的，以及所有已过期的
    )

    expired_issues = []
    upcoming_issues = []

    for issue in issues_to_check:
        if issue.due_date and issue.due_date <= today and issue.status != "紧急":
            issue.status = "紧急"
            issue.severity = "紧急"
            expired_issues.append(issue)
            logger.info("Updated expired issue: %s - %s", issue.id, issue.description)
        elif issue.due_date and today < issue.due_date <= seven_days_later and issue.status == "待处理":
            issue.status = "处理中"
            upcoming_issues.append(issue)
            logger.info("Updated upcoming issue: %s - %s", issue.id, issue.description)

    # 批量更新，减少数据库查询
    if expired_issues:
        ComplianceIssue.objects.bulk_update(expired_issues, ["status", "severity"])
        _notify_escalated_issues(expired_issues, today)
    if upcoming_issues:
        ComplianceIssue.objects.bulk_update(upcoming_issues, ["status"])

    updated_count = len(expired_issues) + len(upcoming_issues)

    logger.info("check_compliance_due_dates task finished. Updated %d issues.", updated_count)


def _notify_escalated_issues(issues, today):
    """合规问题过期升级为紧急后,紧急通知项目负责人(P0-L)。

    dedupe_key 按 问题 + 日期 粒度:同日任务多次执行不重复发通知。
    """
    from notifications.service import NotificationService

    for issue in issues:
        manager = getattr(issue.project, "manager", None)
        if manager is None:
            logger.debug("合规问题 %s 所属项目无负责人,跳过到期通知", issue.id)
            continue
        NotificationService.create(
            user=manager,
            type="compliance_due",
            title=f"合规问题已逾期:{issue.project.name}",
            content=f"{issue.description[:200]}(系统已自动升级为紧急,请尽快处理)",
            dedupe_key=f"compliance_due:{issue.id}:{today.isoformat()}",
            priority=Notification.PRIORITY_URGENT,
        )
