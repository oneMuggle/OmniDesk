from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SensorViewSet, SensorMovementViewSet, CalibrationReminderViewSet

router = DefaultRouter()
router.register(r'sensors', SensorViewSet)
router.register(r'sensor-movements', SensorMovementViewSet)
router.register(r'calibration-reminders', CalibrationReminderViewSet)

urlpatterns = [
    path('', include(router.urls)),
]