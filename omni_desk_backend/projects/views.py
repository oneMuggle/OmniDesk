from rest_framework import exceptions, permissions, viewsets

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
