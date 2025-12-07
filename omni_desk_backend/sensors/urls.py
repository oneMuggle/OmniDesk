from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SensorViewSet, CalibrationRecordViewSet

router = DefaultRouter()
router.register(r'sensors', SensorViewSet)
router.register(r'calibration-records', CalibrationRecordViewSet)

urlpatterns = [
    path('', include(router.urls)),
]