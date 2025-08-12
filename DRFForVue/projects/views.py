from rest_framework import viewsets, permissions
from .models import Project
from .serializers import ProjectSerializer

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # 允许管理员查看所有项目，非管理员只能查看自己负责的项目
        if self.request.user.is_staff:
            return Project.objects.all()
        return Project.objects.filter(manager=self.request.user)

    def perform_create(self, serializer):
        # 创建项目时，如果未指定manager，则默认为当前用户
        if not serializer.validated_data.get('manager'):
            serializer.save(manager=self.request.user)
        else:
            serializer.save()