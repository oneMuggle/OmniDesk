from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.contrib.auth.models import Group
from django.db import transaction
from .models import PageRoute, GroupPagePermission
from .serializers import GroupSerializer, PageRouteSerializer


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all().order_by('id')
    serializer_class = GroupSerializer
    permission_classes = [IsAdminUser]

class PageRouteViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = PageRoute.objects.filter(parent__isnull=True).order_by('id')
    serializer_class = PageRouteSerializer

class GroupPermissionView(APIView):
    def get(self, request, group_id):
        try:
            group = Group.objects.get(id=group_id)
            permissions = GroupPagePermission.objects.filter(group=group)
            page_ids = [p.page.id for p in permissions]
            return Response(page_ids)
        except Group.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def put(self, request, group_id):
        try:
            group = Group.objects.get(id=group_id)
        except Group.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        page_ids = request.data.get('permissions', [])

        try:
            with transaction.atomic():
                # First, delete all existing permissions for the group.
                GroupPagePermission.objects.filter(group=group).delete()

                # Filter for valid page IDs to prevent IntegrityError on bulk_create.
                valid_page_ids = PageRoute.objects.filter(id__in=page_ids).values_list('id', flat=True)

                new_permissions = [
                    GroupPagePermission(group=group, page_id=page_id)
                    for page_id in valid_page_ids
                ]

                if new_permissions:
                    GroupPagePermission.objects.bulk_create(new_permissions)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception:
            # The transaction will be rolled back automatically on any exception.
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
