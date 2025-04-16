from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Config
from .serializers import ConfigSerializer

class ConfigViewSet(viewsets.ModelViewSet):
    queryset = Config.objects.all()
    serializer_class = ConfigSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'key'

class ConfigView(APIView):
    """
    API endpoint for getting/setting OLLAMA endpoint configuration
    """
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
