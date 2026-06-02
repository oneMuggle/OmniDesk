from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CalibrationReminderViewSet,
    SensorCalibrationViewSet,
    SensorMovementViewSet,
    SensorViewSet,
)

router = DefaultRouter()
router.register(r"sensors", SensorViewSet, basename="sensor")
router.register(r"sensor-movements", SensorMovementViewSet)
router.register(r"sensor-calibrations", SensorCalibrationViewSet)
router.register(r"calibration-reminders", CalibrationReminderViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
