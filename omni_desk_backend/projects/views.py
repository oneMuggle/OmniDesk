from rest_framework import viewsets, permissions, exceptions
from .models import Project
from .serializers import ProjectSerializer
from .permissions import IsProjectOwnerOrAdmin

class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous:
            return Project.objects.none()

        if user.role == 'admin':
            return Project.objects.all()
        elif user.role == 'manager':
            return Project.objects.filter(manager=user)
        
        # Regular users should not see any projects directly
        # They might access them through other relations, but not list them.
        return Project.objects.none()

    def perform_create(self, serializer):
        # Only managers can create projects, and they are set as the manager.
        if self.request.user.role == 'manager':
            serializer.save(manager=self.request.user)
        elif self.request.user.role == 'admin':
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