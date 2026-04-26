from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Memo
from .serializers import MemoSerializer


class MemoViewSet(viewsets.ModelViewSet):
    """
    一个用于查看和编辑用户备忘录的视图集。
    """
    serializer_class = MemoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        此视图应返回经过身份验证的用户的所有备忘录列表。
        """
        user = self.request.user
        return Memo.objects.filter(user=user)

    def perform_create(self, serializer):
        """
        创建新备忘录时，将用户设置为当前登录用户。
        """
        serializer.save(user=self.request.user)
