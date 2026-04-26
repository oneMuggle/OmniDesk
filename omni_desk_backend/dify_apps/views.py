
# Create your views here.
from rest_framework import permissions, viewsets

from .models import DifyApp
from .serializers import DifyAppSerializer


class DifyAppViewSet(viewsets.ModelViewSet):
    queryset = DifyApp.objects.all()
    serializer_class = DifyAppSerializer
    permission_classes = [permissions.IsAuthenticated]
