from rest_framework import viewsets, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser # 导入 IsAdminUser

from .models import Config, PageConfig # 导入 PageConfig
from .serializers import ConfigSerializer, PageConfigSerializer # 导入 PageConfigSerializer

class ConfigViewSet(viewsets.ModelViewSet):
    queryset = Config.objects.all()
    serializer_class = ConfigSerializer
    permission_classes = []
    lookup_field = 'key'

    def get_permissions(self):
        if self.action in ['create', 'update', 'destroy']:
            return []
        return super().get_permissions()

class SystemConfigView(APIView):
    """系统配置API"""
    permission_classes = []
        
    def get(self, request, format=None):
        try:
            config = Config.objects.get(key='OLLAMA_ENDPOINT')
            return Response({'OLLAMA_ENDPOINT': config.value})
        except Config.DoesNotExist:
            return Response({'OLLAMA_ENDPOINT': ''})

    def post(self, request, format=None):
        Config.objects.update_or_create(
            key='OLLAMA_ENDPOINT',
            defaults={'value': request.data.get('OLLAMA_ENDPOINT', '')}
        )
        return Response({'status': 'success'})

class UserConfigView(APIView):
    """用户配置API"""
    permission_classes = []

class PageConfigListView(generics.ListCreateAPIView):
    queryset = PageConfig.objects.all()
    serializer_class = PageConfigSerializer
    permission_classes = [IsAdminUser] # 只有管理员可以访问

class PageConfigDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PageConfig.objects.all()
    serializer_class = PageConfigSerializer
    permission_classes = [IsAdminUser] # 只有管理员可以访问
    lookup_field = 'page_path' # 根据 page_path 进行查找
