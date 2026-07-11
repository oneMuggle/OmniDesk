from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FileProcessingViewSet

router = DefaultRouter()
router.register(r"file", FileProcessingViewSet, basename="file")

urlpatterns = [
    path("", include(router.urls)),
]
