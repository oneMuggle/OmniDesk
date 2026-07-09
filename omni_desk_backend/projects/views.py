from rest_framework import exceptions, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from paperless_proxy.services.upload import PaperlessUploadService

from .models import Project
from .permissions import IsProjectOwnerOrAdmin
from .serializers import ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous:
            return Project.objects.none()

        if user.is_superuser or user.groups.filter(name="Admin").exists():
            return Project.objects.all()
        elif user.groups.filter(name="Manager").exists():
            return Project.objects.filter(manager=user)

        # Regular users should not see any projects directly
        # They might access them through other relations, but not list them.
        return Project.objects.none()

    def perform_create(self, serializer):
        # Only managers can create projects, and they are set as the manager.
        if self.request.user.groups.filter(name="Manager").exists():
            serializer.save(manager=self.request.user)
        elif self.request.user.is_superuser or self.request.user.groups.filter(name="Admin").exists():
            # Admins can create projects and must specify a manager.
            serializer.save()
        else:
            # This case should be blocked by permissions, but as a safeguard:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to create projects.")

    def check_permissions(self, request):
        try:
            super().check_permissions(request)
        except exceptions.PermissionDenied:
            if not request.user.is_authenticated:
                raise exceptions.NotAuthenticated()
            raise

    @action(
        detail=True,
        methods=['post'],
        parser_classes=[MultiPartParser, FormParser],
        url_path='upload_document',
        url_name='upload-document',
    )
    def upload_document(self, request, pk=None):
        """上传项目文档,通过 paperless_proxy 异步投递到 paperless-ngx。"""
        project = self.get_object()

        # 复用对象级权限:仅项目负责人 / Admin / 超级用户可上传
        self.check_object_permissions(request, project)

        file = request.FILES.get('file')
        if not file:
            return Response(
                {'detail': '缺少 file 字段'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = PaperlessUploadService.queue_upload(
                file=file,
                filename=file.name,
                title=request.data.get('title') or file.name,
                source_type='project_document',
                source_id=project.id,
                owner=request.user,
                tags=request.data.get('tags'),
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result, status=status.HTTP_201_CREATED)
