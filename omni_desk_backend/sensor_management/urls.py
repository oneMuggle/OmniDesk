from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SensorViewSet, SensorCategoryViewSet, StorageLocationViewSet

router = DefaultRouter()
router.register(r'sensors', SensorViewSet, basename='sensor')
router.register(r'categories', SensorCategoryViewSet)
router.register(r'storage-locations', StorageLocationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]