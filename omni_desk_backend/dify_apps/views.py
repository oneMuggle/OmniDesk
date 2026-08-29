# Create your views here.
from rest_framework import permissions, viewsets

from observability import get_logger

from .models import DifyApp
from .serializers import DifyAppSerializer

logger = get_logger(__name__, "dify_apps")


class DifyAppViewSet(viewsets.ModelViewSet):
    queryset = DifyApp.objects.all()
    serializer_class = DifyAppSerializer

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        logger.info("dify_apps.view.entered", extra={"event": "dify_apps.view.entered"})
        return super().list(request, *args, **kwargs)
