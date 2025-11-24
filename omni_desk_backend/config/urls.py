from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import PageVisibilityViewSet, get_ollama_config

router = DefaultRouter()
router.register(r'page-visibility', PageVisibilityViewSet, basename='page-visibility')

urlpatterns = [
    path('config/', get_ollama_config, name='get_ollama_config'),
] + router.urls
