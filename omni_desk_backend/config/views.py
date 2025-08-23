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

from rest_framework import viewsets
from .models import OllamaConfig
from .serializers import OllamaConfigSerializer

class OllamaConfigViewSet(viewsets.ModelViewSet):
    queryset = OllamaConfig.objects.all()
    serializer_class = OllamaConfigSerializer
    pagination_class = None

import requests

class OllamaModelsView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        api_endpoint = request.data.get('api_endpoint')
        if not api_endpoint:
            return Response({"error": "api_endpoint is required"}, status=400)

        try:
            # Ensure the endpoint points to the /api directory
            if not api_endpoint.endswith('/api'):
                if api_endpoint.endswith('/'):
                    api_endpoint += 'api'
                else:
                    api_endpoint += '/api'
            
            # Make a request to the ollama /api/tags endpoint
            response = requests.get(f"{api_endpoint}/tags")
            response.raise_for_status() # Raise an exception for bad status codes
            models = response.json().get('models', [])
            model_names = [model['name'] for model in models]
            return Response(model_names)
        except requests.exceptions.RequestException as e:
            return Response({"error": f"Failed to connect to Ollama API: {e}"}, status=500)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
