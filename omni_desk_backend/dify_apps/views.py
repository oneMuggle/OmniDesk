from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from .models import DifyApp
from .serializers import DifyAppSerializer

class DifyAppViewSet(viewsets.ModelViewSet):
    queryset = DifyApp.objects.all()
    serializer_class = DifyAppSerializer
    # 权限可以根据实际需求调整，例如IsAdminUser, IsAuthenticatedOrReadOnly等
    # permission_classes = [permissions.IsAuthenticated]
