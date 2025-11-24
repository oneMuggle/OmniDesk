from rest_framework import viewsets
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action # 导入 action 装饰器
from .models import ComplianceIssue
from .serializers import ComplianceIssueSerializer
from documents.models import Book, DocumentTemplate
from projects.models import Project

class ComplianceIssueViewSet(viewsets.ModelViewSet):
    queryset = ComplianceIssue.objects.all()
    serializer_class = ComplianceIssueSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'issue_type', 'status', 'severity', 'due_date']
    search_fields = ['description', 'location']
    ordering_fields = ['created_at', 'due_date', 'severity']

    def get_queryset(self):
        # 管理员可以查看所有问题，非管理员只能查看与自己负责项目相关的问题
        if self.request.user.is_staff:
            return ComplianceIssue.objects.all()
        
        # 筛选与用户负责项目相关的问题
        user_projects = Project.objects.filter(manager=self.request.user)
        return ComplianceIssue.objects.filter(project__in=user_projects)

    def perform_create(self, serializer):
        # 确保创建问题时，关联的项目是当前用户负责的，或者用户是管理员
        project = serializer.validated_data.get('project')
        if not self.request.user.is_staff and project.manager != self.request.user:
            raise PermissionDenied("您无权在此项目下创建合规问题。")
        serializer.save()

    def perform_update(self, serializer):
        # 确保更新问题时，关联的项目是当前用户负责的，或者用户是管理员
        project = serializer.instance.project
        if not self.request.user.is_staff and project.manager != self.request.user:
            raise PermissionDenied("您无权修改此项目下的合规问题。")
        serializer.save()

    def perform_destroy(self, instance):
        # 确保删除问题时，关联的项目是当前用户负责的，或者用户是管理员
        project = instance.project
        if not self.request.user.is_staff and project.manager != self.request.user:
            raise PermissionDenied("您无权删除此项目下的合规问题。")
        instance.delete()

    @action(detail=False, methods=['get'], url_path='unread_count')
    def unread_count(self, request):
        # 假设“未读”是指状态为“待处理”或“处理中”的问题
        # 并且只计算与当前用户负责项目相关的问题（如果用户不是管理员）
        if request.user.is_staff:
            count = ComplianceIssue.objects.filter(status__in=['待处理', '处理中']).count()
        else:
            user_projects = Project.objects.filter(manager=request.user)
            count = ComplianceIssue.objects.filter(
                project__in=user_projects,
                status__in=['待处理', '处理中']
            ).count()
        return Response({'unread_count': count})