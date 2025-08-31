from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SystemConfigView, PageConfigListView, PageConfigDetailView, OllamaConfigViewSet, OllamaModelsView

router = DefaultRouter()
router.register(r'ollama-configs', OllamaConfigViewSet, basename='ollamaconfig')

urlpatterns = [
    path('', SystemConfigView.as_view(), name='config'),
    path('pages/', PageConfigListView.as_view(), name='page-config-list'),
    path('pages/<str:page_path>/', PageConfigDetailView.as_view(), name='page-config-detail'),
    path('ollama-models/', OllamaModelsView.as_view(), name='ollama-models'),
    path('', include(router.urls)),
]
