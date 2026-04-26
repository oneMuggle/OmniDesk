from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RagflowConfigViewSet, ragflow_configs_view

router = DefaultRouter()
router.register(r'configs', RagflowConfigViewSet)

urlpatterns = [
    path('configs/', ragflow_configs_view, name='ragflow-configs-simple'),
    path('', include(router.urls)),
]
