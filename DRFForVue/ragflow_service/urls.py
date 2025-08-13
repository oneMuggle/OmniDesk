from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RagflowConfigViewSet

router = DefaultRouter()
router.register(r'configs', RagflowConfigViewSet)

urlpatterns = [
    path('', include(router.urls)),
]