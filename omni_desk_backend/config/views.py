from django.conf import settings
from django.contrib.auth.models import Group
from django.http import JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from users.permissions import IsAdminOrReadOnly

from .models import OllamaConfig, Page, PageVisibility
from .serializers import GroupSerializer, OllamaConfigSerializer, PageSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def get_ollama_config(request):
    """
    返回Ollama配置。
    """
    return Response({"OLLAMA_ENDPOINT": settings.OLLAMA_BASE_URL})


class PageVisibilityViewSet(viewsets.ViewSet):
    """
    一个用于查看和编辑页面可见性的ViewSet。
    """

    permission_classes = [IsAdminOrReadOnly]

    def list(self, request):
        """
        返回所有页面、所有组以及它们之间的可见性关系。
        """
        pages = Page.objects.all()
        groups = Group.objects.all()
        visibility = PageVisibility.objects.all()

        page_serializer = PageSerializer(pages, many=True)
        group_serializer = GroupSerializer(groups, many=True)

        visibility_dict = {f"{v.page.id}-{v.group.id}": v.is_visible for v in visibility}

        return Response(
            {
                "pages": page_serializer.data,
                "groups": group_serializer.data,
                "visibility": visibility_dict,
            }
        )

    def create(self, request):
        """
        创建或更新一个页面的可见性设置。
        """
        page_id = request.data.get("page_id")
        group_id = request.data.get("group_id")
        is_visible = request.data.get("is_visible")

        if page_id is None or group_id is None or is_visible is None:
            return Response({"error": "Missing page_id, group_id, or is_visible"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            page = Page.objects.get(pk=page_id)
            group = Group.objects.get(pk=group_id)
        except (Page.DoesNotExist, Group.DoesNotExist):
            return Response({"error": "Invalid page_id or group_id"}, status=status.HTTP_404_NOT_FOUND)

        obj, created = PageVisibility.objects.update_or_create(
            page=page, group=group, defaults={"is_visible": is_visible}
        )

        return Response({"status": "success"}, status=status.HTTP_200_OK)


class OllamaConfigViewSet(viewsets.ModelViewSet):
    """
    用于管理 Ollama 配置的 ViewSet。
    """

    queryset = OllamaConfig.objects.all()
    serializer_class = OllamaConfigSerializer
    permission_classes = [IsAdminOrReadOnly]


def ollama_configs_view(request):
    """
    一个简单的视图，返回一个固定的 JSON 响应。
    """
    return JsonResponse({"status": "ok"})
