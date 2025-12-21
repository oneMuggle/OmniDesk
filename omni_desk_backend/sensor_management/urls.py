from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SensorViewSet,
    SensorCategoryViewSet,
    StorageLocationViewSet,
    SensorMovementViewSet,
    SensorCalibrationViewSet,
    CalibrationReminderViewSet,
)

router = DefaultRouter()
router.register(r'sensors', SensorViewSet, basename='sensor')
router.register(r'categories', SensorCategoryViewSet)
router.register(r'storage-locations', StorageLocationViewSet)
router.register(r'sensor-movements', SensorMovementViewSet)
router.register(r'sensor-calibrations', SensorCalibrationViewSet)
router.register(r'calibration-reminders', CalibrationReminderViewSet)

urlpatterns = [
    path('', include(router.urls)),
]