"""P0-L 合规到期升级接入 NotificationService 测试

- 过期 ComplianceIssue 经 check_compliance_due_dates 升级为"紧急",
  并向项目负责人发送 compliance_due 紧急通知
- 项目无负责人时安全跳过
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from compliance.models import ComplianceIssue
from compliance.tasks import check_compliance_due_dates
from notifications.models import Notification
from projects.models import Project
from users.models import CustomUser


@pytest.fixture
def manager(db):
    return CustomUser.objects.create_user(username="compliance_mgr", password="pass12345")


def _make_issue(project, days_overdue=3):
    return ComplianceIssue.objects.create(
        project=project,
        issue_type="内容缺失",
        description=" overdue " * 30,
        status="待处理",
        severity="中",
        due_date=timezone.localdate() - timedelta(days=days_overdue),
    )


@pytest.mark.django_db
class TestDueNotification:
    def test_expired_issue_escalated_and_manager_notified(self, manager):
        project = Project.objects.create(name="合规项目A", manager=manager)
        issue = _make_issue(project)

        check_compliance_due_dates()

        issue.refresh_from_db()
        assert issue.status == "紧急"
        assert issue.severity == "紧急"

        note = Notification.objects.filter(type="compliance_due").first()
        assert note is not None
        assert note.user_id == manager.id
        assert note.priority == Notification.PRIORITY_URGENT
        assert note.dedupe_key == f"compliance_due:{issue.id}:{timezone.localdate().isoformat()}"

    def test_issue_without_manager_skips_notification(self):
        project = Project.objects.create(name="无负责人项目", manager=None)
        _make_issue(project)

        check_compliance_due_dates()

        assert not Notification.objects.filter(type="compliance_due").exists()

    def test_future_issue_not_escalated(self, manager):
        project = Project.objects.create(name="合规项目B", manager=manager)
        issue = ComplianceIssue.objects.create(
            project=project,
            issue_type="不规范",
            description="未到期",
            status="已解决",
            severity="低",
            due_date=timezone.localdate() + timedelta(days=30),
        )

        check_compliance_due_dates()

        issue.refresh_from_db()
        assert issue.status == "已解决"
        assert not Notification.objects.filter(type="compliance_due").exists()
