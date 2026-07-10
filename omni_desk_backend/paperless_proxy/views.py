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
from .serializers import (
    OutboxItemSerializer,
    DocumentBindingSerializer,
    PaperlessHealthSerializer,
    UserPaperlessBindingSerializer,
)
from .permissions import IsAdmin, IsBindingOwnerOrAdmin
from .services.outbox import OutboxService
from .services.client import PaperlessClient
from .exceptions import PaperlessAuthError, PaperlessNotFoundError, PaperlessUnavailableError


class UploadView(APIView):
    """POST /api/paperless/upload/ — multipart 上传,入 outbox"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .services.upload import PaperlessUploadService
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"detail": "缺少 file 字段"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 显式校验 source_id:multipart 中缺失或非法值都会导致后续 unique_together 冲突
        raw_source_id = request.data.get("source_id")
        if raw_source_id is None:
            return Response(
                {"detail": "缺少 source_id 字段"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            source_id = int(raw_source_id)
            if source_id <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"detail": "source_id 必须是正整数"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # tags:multipart 不能直接传递数组,QueryDict 取值可能为字符串(单值或逗号分隔)或 list
        raw_tags = request.data.get("tags")
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()] or None
        elif isinstance(raw_tags, list):
            tags = raw_tags
        else:
            tags = None

        try:
            result = PaperlessUploadService.queue_upload(
                file=file,
                filename=file.name,
                title=request.data.get("title") or file.name,
                source_type=request.data.get("source_type", "project_document"),
                source_id=source_id,
                owner=request.user,
                correspondent=request.data.get("correspondent"),
                document_type=request.data.get("document_type"),
                tags=tags,
            )
        except (ValueError, TypeError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result, status=status.HTTP_201_CREATED)


class OutboxViewSet(viewsets.ModelViewSet):
    """Outbox 管理(admin 限定)"""

    queryset = OutboxItem.objects.all()
    serializer_class = OutboxItemSerializer
    permission_classes = [IsAdmin]
    http_method_names = ["get", "post", "delete", "head", "options"]  # 禁 PUT/PATCH
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "operation"]

    def destroy(self, request, *args, **kwargs):
        """仅 dead 状态可删除,避免误删正在处理的项"""
        outbox = self.get_object()
        if outbox.status != "dead":
            return Response(
                {"detail": f"只能删除死信(当前 status={outbox.status})"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

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


class DocumentBindingViewSet(viewsets.ModelViewSet):
    """DocumentBinding GET/PATCH/DELETE — POST /documents/ via 405, use POST /upload/ instead"""

    queryset = DocumentBinding.objects.all()
    serializer_class = DocumentBindingSerializer
    permission_classes = [IsAuthenticated, IsBindingOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["source_type", "source_id", "owner", "paperless_id"]
    http_method_names = ["get", "patch", "delete", "head", "options"]  # 禁 POST(upload 走 /upload/)

    def get_queryset(self):
        """非管理员只看自己的 binding;IsBindingOwnerOrAdmin 仅保护 detail"""
        qs = DocumentBinding.objects.all()
        if not self.request.user.is_staff:
            qs = qs.filter(owner=self.request.user)
        return qs

    def update(self, request, *args, **kwargs):
        """PATCH → 入 update_metadata outbox(不直接改 binding)"""
        binding = self.get_object()
        fields = {
            k: v for k, v in request.data.items()
            if k in ("title", "correspondent_id", "extra_metadata", "tags")
        }
        outbox = OutboxService.queue_update_metadata(binding, fields, created_by=request.user)
        return Response(
            {"binding_id": binding.id, "outbox_id": outbox.id, "status": outbox.status},
            status=status.HTTP_202_ACCEPTED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """DELETE → 入 delete outbox(worker 异步删 binding + paperless)"""
        binding = self.get_object()
        outbox = OutboxService.queue_delete(binding, created_by=request.user)
        return Response(
            {"binding_id": binding.id, "outbox_id": outbox.id, "status": outbox.status},
            status=status.HTTP_202_ACCEPTED,
        )
