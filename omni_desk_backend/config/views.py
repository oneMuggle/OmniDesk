from rest_framework import viewsets, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.exceptions import ValidationError
from rest_framework import status
from django.db import IntegrityError # Import IntegrityError
import logging
import requests

from .models import Config, PageConfig, OllamaConfig
from .serializers import ConfigSerializer, PageConfigSerializer, OllamaConfigSerializer

logger = logging.getLogger(__name__)

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

class OllamaConfigViewSet(viewsets.ModelViewSet):
    queryset = OllamaConfig.objects.all()
    serializer_class = OllamaConfigSerializer
    pagination_class = None

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except ValidationError as e:
            logger.error(f"Validation Error during OllamaConfig creation: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError as e: # Catch IntegrityError specifically
            logger.error(f"Integrity Error during OllamaConfig creation: {e}")
            return Response({"detail": "Alias already exists. Please choose a different alias."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("An unexpected error occurred during OllamaConfig creation:") # Log full traceback
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except ValidationError as e:
            logger.error(f"Validation Error during OllamaConfig update: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError as e: # Catch IntegrityError specifically
            logger.error(f"Integrity Error during OllamaConfig update: {e}")
            return Response({"detail": "Alias already exists. Please choose a different alias."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("An unexpected error occurred during OllamaConfig update:") # Log full traceback
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OllamaModelsView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        api_endpoint = request.data.get('api_endpoint')
        if not api_endpoint:
            return Response({"error": "api_endpoint is required"}, status=400)

        try:
            # Ensure the api_endpoint has a trailing slash for proper joining
            if not api_endpoint.endswith('/'):
                api_endpoint += '/'
            
            # Make a request to the ollama /v1/models endpoint as per user's requirement
            response = requests.get(f"{api_endpoint}v1/models")
            response.raise_for_status() # Raise an exception for bad status codes
            models = response.json().get('models', [])
            model_names = [model['name'] for model in models]
            return Response(model_names)
        except requests.exceptions.RequestException as e:
            return Response({"error": f"Failed to connect to Ollama API: {e}"}, status=500)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
