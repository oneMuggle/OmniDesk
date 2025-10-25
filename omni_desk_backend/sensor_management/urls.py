from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SensorViewSet, SensorMovementViewSet, CalibrationReminderViewSet, SensorCategoryViewSet, StorageLocationViewSet, SensorCalibrationViewSet

router = DefaultRouter()
router.register(r'sensors', SensorViewSet)
router.register(r'sensor-movements', SensorMovementViewSet)
router.register(r'calibration-reminders', CalibrationReminderViewSet)
router.register(r'sensor-categories', SensorCategoryViewSet)
router.register(r'storage-locations', StorageLocationViewSet)
router.register(r'sensor-calibrations', SensorCalibrationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]