from django.urls import path
from .views import SystemConfigView, PageConfigListView, PageConfigDetailView

urlpatterns = [
    path('', SystemConfigView.as_view(), name='config'),
    path('pages/', PageConfigListView.as_view(), name='page-config-list'),
    path('pages/<str:page_path>/', PageConfigDetailView.as_view(), name='page-config-detail'),
]

from rest_framework.routers import DefaultRouter
from .views import OllamaConfigViewSet

router = DefaultRouter()
router.register(r'ollama-configs', OllamaConfigViewSet, basename='ollamaconfig')

urlpatterns = router.urls

from django.urls import path
from .views import OllamaModelsView

urlpatterns.append(path('ollama-models/', OllamaModelsView.as_view(), name='ollama-models'))
