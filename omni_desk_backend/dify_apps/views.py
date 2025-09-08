from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets, permissions
from .models import DifyApp
from .serializers import DifyAppSerializer

class DifyAppViewSet(viewsets.ModelViewSet):
    queryset = DifyApp.objects.all()
    serializer_class = DifyAppSerializer
    permission_classes = [permissions.IsAuthenticated]
