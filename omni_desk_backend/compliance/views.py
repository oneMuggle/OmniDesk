from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from .models import ComplianceIssue
from .serializers import ComplianceIssueSerializer
from .services.compliance_engine import ComplianceChecker


class ComplianceIssueViewSet(viewsets.ModelViewSet):
    queryset = ComplianceIssue.objects.all()
    serializer_class = ComplianceIssueSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["project", "issue_type", "status", "severity", "due_date"]
    search_fields = ["description", "location"]
    ordering_fields = ["created_at", "due_date", "severity"]

    def get_queryset(self):
        return ComplianceChecker.get_visible_issues(self.request.user)

    def perform_create(self, serializer):
        project = serializer.validated_data.get("project")
        if not self.request.user.is_staff and project.manager != self.request.user:
            raise PermissionDenied("您无权在此项目下创建合规问题。")
        serializer.save()

    def perform_update(self, serializer):
        if not ComplianceChecker.can_modify_issue(self.request.user, serializer.instance):
            raise PermissionDenied("您无权修改此项目下的合规问题。")
        serializer.save()

    def perform_destroy(self, instance):
        if not ComplianceChecker.can_modify_issue(self.request.user, instance):
            raise PermissionDenied("您无权删除此项目下的合规问题。")
        instance.delete()

    @action(detail=False, methods=["get"], url_path="unread_count")
    def unread_count(self, request):
        count = ComplianceChecker.get_unread_count(request.user)
        return Response({"unread_count": count})

    @action(detail=True, methods=["post"])
    def upload(self, request, pk=None):
        """上传合规报告,通过 paperless_proxy 异步投递到 paperless-ngx"""
        from paperless_proxy.services.upload import PaperlessUploadService

        issue = self.get_object()
        if not ComplianceChecker.can_modify_issue(request.user, issue):
            raise PermissionDenied("您无权在此项目下上传合规报告。")
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "缺少 file 字段"}, status=400)
        try:
            result = PaperlessUploadService.queue_upload(
                file=file,
                filename=file.name,
                title=request.data.get("title") or file.name,
                source_type="compliance_report",
                source_id=issue.id,
                owner=request.user,
                tags=request.data.get("tags"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(result, status=201)
