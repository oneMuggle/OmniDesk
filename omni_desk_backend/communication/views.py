from rest_framework import permissions, viewsets
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated

from observability import get_logger

from .models import Comment, Post
from .serializers import CommentSerializer, PostSerializer

logger = get_logger(__name__, "communication")


class IsAuthorOrReadOnly(permissions.BasePermission):
    """对象级权限(P0-D):读操作放行认证用户,写/删仅限作者本人。"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.author_id == request.user.id


class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]
    queryset = (
        Post.objects.select_related("author")
        .prefetch_related("comments__author")
        .filter(is_archived=False)
        .order_by("-created_at")
    )

    def list(self, request, *args, **kwargs):
        logger.info("communication.view.entered", extra={"event": "communication.view.entered"})
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]
    queryset = Comment.objects.select_related("author", "post").all()

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, post_id=self.kwargs["post_pk"])

    def get_queryset(self):
        # 补回类级 queryset 的 select_related(get_queryset 重写会丢失),避免逐条评论查询 author
        return Comment.objects.filter(post_id=self.kwargs["post_pk"]).select_related("author").order_by("created_at")
