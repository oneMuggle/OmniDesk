"""Compliance business logic: permission checks and query helpers."""

from typing import cast


class ComplianceChecker:
    """Compliance issue query and permission management."""

    @staticmethod
    def get_visible_issues(user):
        """Return queryset of compliance issues visible to the user."""
        from compliance.models import ComplianceIssue
        from projects.models import Project

        if user.is_staff:
            return ComplianceIssue.objects.select_related("project", "document_book", "document_template")

        user_projects = Project.objects.filter(manager=user)
        return ComplianceIssue.objects.filter(project__in=user_projects).select_related(
            "project", "document_book", "document_template"
        )

    @staticmethod
    def can_modify_issue(user, issue) -> bool:
        """Check if user has permission to modify a compliance issue."""
        # user.is_staff 推断为 Any（无 django-stubs），cast 收紧返回类型
        return cast(bool, user.is_staff or issue.project.manager == user)

    @staticmethod
    def get_unread_count(user) -> int:
        """Count unresolved compliance issues visible to the user."""
        from compliance.models import ComplianceIssue
        from projects.models import Project

        if user.is_staff:
            # QuerySet.count() 在无 django-stubs 时返回 Any，cast 收紧
            return cast(int, ComplianceIssue.objects.filter(status__in=["待处理", "处理中"]).count())

        user_projects = Project.objects.filter(manager=user)
        return cast(
            int, ComplianceIssue.objects.filter(project__in=user_projects, status__in=["待处理", "处理中"]).count()
        )
