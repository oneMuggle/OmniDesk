from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CalibrationRecordViewSet, SensorViewSet

router = DefaultRouter()
router.register(r'sensors', SensorViewSet)
router.register(r'calibration-records', CalibrationRecordViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
