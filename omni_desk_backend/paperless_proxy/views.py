import os

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from .models import OutboxItem, PaperlessHealth, UserPaperlessBinding, DocumentBinding
from .serializers import OutboxItemSerializer, PaperlessHealthSerializer, UserPaperlessBindingSerializer
from .permissions import IsAdmin, IsBindingOwnerOrAdmin
from .services.outbox import OutboxService
from .services.client import PaperlessClient
from .exceptions import PaperlessAuthError, PaperlessNotFoundError, PaperlessUnavailableError


class OutboxViewSet(viewsets.ReadOnlyModelViewSet):
    """Outbox 管理(admin 限定)"""

    queryset = OutboxItem.objects.all()
    serializer_class = OutboxItemSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "operation"]

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        outbox = self.get_object()
        if outbox.status != "dead":
            return Response(
                {"detail": f"只能重试死信(当前 status={outbox.status})"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        OutboxService.retry_dead(outbox)
        return Response(OutboxItemSerializer(outbox).data)


class HealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        health = PaperlessHealth.get_singleton()
        return Response(PaperlessHealthSerializer(health).data)


class BindView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bind = UserPaperlessBinding.objects.filter(user=request.user, is_active=True).first()
        if not bind:
            return Response({"bound": False})
        return Response(
            {
                "bound": True,
                **UserPaperlessBindingSerializer(bind).data,
            }
        )

    def delete(self, request):
        UserPaperlessBinding.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        if not username or not password:
            return Response({"detail": "username and password required"}, status=400)
        client = PaperlessClient()
        try:
            client.post_token(username, password)
            user_info = client.get_user_by_username(username)
        except PaperlessAuthError as e:
            return Response({"detail": str(e)}, status=401)
        except PaperlessNotFoundError:
            return Response({"detail": f"paperless 用户 {username} 不存在"}, status=404)
        bind, _ = UserPaperlessBinding.objects.update_or_create(
            user=request.user,
            defaults={
                "paperless_user_id": user_info["id"],
                "paperless_username": user_info["username"],
                "is_active": True,
            },
        )
        return Response(UserPaperlessBindingSerializer(bind).data, status=201)


class BindStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return BindView().get(request)


class DocumentDownloadView(APIView):
    """下载 paperless 文档原始内容;不可用时回退本地缓存(X-Degraded: true)"""

    permission_classes = [IsAuthenticated, IsBindingOwnerOrAdmin]

    def get(self, request, binding_id):
        binding = get_object_or_404(DocumentBinding, pk=binding_id)
        self.check_object_permissions(request, binding)
        client = PaperlessClient()
        cache_path = _get_cache_path(binding.paperless_id)
        try:
            content = client.download(binding.paperless_id)
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "wb") as f:
                f.write(content)
            response = HttpResponse(content, content_type="application/octet-stream")
            response["Content-Disposition"] = f'attachment; filename="{binding.title}"'
            return response
        except PaperlessUnavailableError:
            if os.path.exists(cache_path):
                with open(cache_path, "rb") as f:
                    response = HttpResponse(f.read(), content_type="application/octet-stream")
                    response["X-Degraded"] = "true"
                    response["Content-Disposition"] = f'attachment; filename="{binding.title}"'
                    return response
            return Response(
                {"detail": "paperless 不可用且无本地缓存"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except PaperlessNotFoundError:
            return Response({"detail": "paperless 中文档不存在"}, status=404)


class DocumentPreviewView(APIView):
    """获取 paperless 文档预览图(PNG)"""

    permission_classes = [IsAuthenticated, IsBindingOwnerOrAdmin]

    def get(self, request, binding_id):
        binding = get_object_or_404(DocumentBinding, pk=binding_id)
        self.check_object_permissions(request, binding)
        client = PaperlessClient()
        try:
            content = client.preview(binding.paperless_id)
            return HttpResponse(content, content_type="image/png")
        except PaperlessUnavailableError:
            return Response({"detail": "preview unavailable"}, status=503)
        except PaperlessNotFoundError:
            return Response({"detail": "preview not found"}, status=404)


def _get_cache_path(paperless_id: int) -> str:
    cache_dir = os.path.join(settings.MEDIA_ROOT, settings.PAPERLESS_CACHE_DIR)
    return os.path.join(cache_dir, f"{paperless_id}.bin")


class BindingSyncStatusView(APIView):
    """返回绑定对应的最新 outbox 同步状态"""

    permission_classes = [IsAuthenticated, IsBindingOwnerOrAdmin]

    def get(self, request, binding_id):
        binding = get_object_or_404(DocumentBinding, pk=binding_id)
        self.check_object_permissions(request, binding)
        latest = binding.outbox.order_by("-created_at").first()
        return Response(
            {
                "binding_id": binding.id,
                "paperless_id": binding.paperless_id,
                "sync_status": latest.status if latest else "synced",
            }
        )
