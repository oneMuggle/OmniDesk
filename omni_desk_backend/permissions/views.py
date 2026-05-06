import logging

from django.contrib.auth.models import Group, Permission
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminOrReadOnly

from .models import GroupPagePermission, PageRoute
from .serializers import GroupSerializer, PageRouteSerializer

logger = logging.getLogger(__name__)


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all().order_by('id')
    serializer_class = GroupSerializer
    permission_classes = [IsAdminOrReadOnly]

    def list(self, request, *args, **kwargs):
        logger.info(f"User: {request.user}, is_staff: {request.user.is_staff}")
        return super().list(request, *args, **kwargs)

class PageRouteViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        logger.info(f"User: {request.user}, is_staff: {request.user.is_staff}")
        return super().list(request, *args, **kwargs)
    queryset = PageRoute.objects.filter(parent__isnull=True).order_by('id')
    serializer_class = PageRouteSerializer

class GroupPermissionView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request, group_id):
        try:
            group = Group.objects.get(id=group_id)
            permission_ids = group.permissions.values_list('id', flat=True)
            return Response(list(permission_ids))
        except Group.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def put(self, request, group_id):
        try:
            group = Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        permission_ids = request.data.get('permissions', [])

        try:
            permissions = Permission.objects.filter(id__in=permission_ids)
            group.permissions.set(permissions)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error updating permissions for group {group_id}: {e}")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserPermissionView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        if user.is_superuser:
            # Superuser has all permissions
            pages = PageRoute.objects.all()
        else:
            groups = user.groups.all()
            page_ids = GroupPagePermission.objects.filter(group__in=groups).values_list('page_id', flat=True).distinct()
            pages = PageRoute.objects.filter(id__in=page_ids)

        serializer = PageRouteSerializer(pages, many=True)
        return Response(serializer.data)


class GroupedPermissionsView(APIView):
    """
    Provides a list of all available permissions, grouped by their content type (model).
    """
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request, *args, **kwargs):
        # Eagerly fetch content types to reduce database queries
        permissions = Permission.objects.select_related('content_type').all()

        grouped_permissions = {}
        for perm in permissions:
            # Use model_class() to get the verbose_name of the model if available
            model_class = perm.content_type.model_class()
            if model_class and hasattr(model_class._meta, 'verbose_name'):
                group_name = f"{perm.content_type.app_label} | {model_class._meta.verbose_name}"
            else:
                group_name = f"{perm.content_type.app_label} | {perm.content_type.model}"

            if group_name not in grouped_permissions:
                grouped_permissions[group_name] = []

            grouped_permissions[group_name].append({
                'id': perm.id,
                'name': perm.name,
                'codename': perm.codename
            })

        return Response(grouped_permissions)
