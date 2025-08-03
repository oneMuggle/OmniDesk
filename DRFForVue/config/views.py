from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Config
from .serializers import ConfigSerializer

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
