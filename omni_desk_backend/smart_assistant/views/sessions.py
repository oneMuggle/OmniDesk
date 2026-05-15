from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import SmartAssistantSession
from .serializers import SmartAssistantSessionSerializer


class SessionViewSet(viewsets.ModelViewSet):
    """会话管理：列表/创建/查看/删除"""
    serializer_class = SmartAssistantSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SmartAssistantSession.objects.filter(
            user=self.request.user
        ).order_by('-updated_at')

    def perform_destroy(self, instance):
        if instance.user == self.request.user:
            instance.delete()
