from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import PageVisibilityViewSet, get_ollama_config, ollama_configs_view

router = DefaultRouter()
router.register(r'page-visibility', PageVisibilityViewSet, basename='page-visibility')

urlpatterns = [
    path('config/', get_ollama_config, name='get_ollama_config'),
    path('ollama-configs/', ollama_configs_view, name='ollama_configs_view'),
] + router.urls
