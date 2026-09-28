"""events.views.announcements — 公告/图片上传 ViewSet

拆分自原 events/views.py(Phase 3 优化)。包含:
- AnnouncementViewSet: 公告 CRUD
- ImageUploadView: 图片上传 API
"""

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminOrManagerOrReadOnly, is_privileged_user

from ..models import Announcement
from ..serializers import AnnouncementSerializer, UploadedImageSerializer


class AnnouncementViewSet(viewsets.ModelViewSet):
    # 草稿（无发布时间）排在最前，其余按发布时间倒序
    queryset = Announcement.objects.select_related("author").order_by(
        F("published_at").desc(nulls_first=True), "-created_at"
    )
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]

    def get_queryset(self):
        """草稿（S3-2）只对管理员 / HR 可见。

        列表默认只返回已发布公告；管理员 / HR 带 ``?include_drafts=1`` 才包含草稿（公告管理页）。
        详情、编辑、删除、发布时管理员 / HR 可访问草稿；其他人访问草稿得到 404。
        """
        queryset = super().get_queryset()
        privileged = is_privileged_user(self.request.user)
        if self.action == "list":
            include_drafts = self.request.query_params.get("include_drafts") in ("1", "true")
            if not (privileged and include_drafts):
                queryset = queryset.filter(status=Announcement.STATUS_PUBLISHED)
        elif not privileged:
            queryset = queryset.filter(status=Announcement.STATUS_PUBLISHED)
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """发布草稿：条件更新防止重复发布；发布成功后通知全体用户（作者除外）。"""
        from notifications.signals import notify_announcement_published

        announcement = self.get_object()
        with transaction.atomic():
            updated = Announcement.objects.filter(pk=announcement.pk, status=Announcement.STATUS_DRAFT).update(
                status=Announcement.STATUS_PUBLISHED, published_at=timezone.now(), updated_at=timezone.now()
            )
            if not updated:
                return Response({"detail": "该公告已发布。"}, status=status.HTTP_409_CONFLICT)
            announcement.refresh_from_db()
            notify_announcement_published(announcement)
        return Response(self.get_serializer(announcement).data)


class ImageUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = UploadedImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
