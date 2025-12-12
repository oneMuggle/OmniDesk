from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import PageVisibilityViewSet, get_ollama_config, OllamaConfigViewSet

router = DefaultRouter()
router.register(r'page-visibility', PageVisibilityViewSet, basename='page-visibility')
router.register(r'ollama-configs', OllamaConfigViewSet, basename='ollama-config')

urlpatterns = [
    path('', get_ollama_config, name='get_ollama_config'),
] + router.urls
