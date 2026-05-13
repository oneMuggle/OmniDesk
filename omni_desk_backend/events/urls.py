from django.urls import include, path
from rest_framework.routers import DefaultRouter

from personnel.views import PositionViewSet
from .views import (
    AnnouncementViewSet,
    EquipmentViewSet,
    HolidayViewSet,
    ImageUploadView,
    LeaderSequenceViewSet,
    PersonnelSequenceViewSet,
    ScheduleViewSet,
    TimeSlotViewSet,
    TrialViewSet,
)

router = DefaultRouter()
router.register(r'trials', TrialViewSet, basename='trials')
router.register(r'time-slots', TimeSlotViewSet, basename='time-slots')
router.register(r'schedules', ScheduleViewSet, basename='schedules')
router.register(r'announcements', AnnouncementViewSet, basename='announcements')
router.register(r'personnel-sequences', PersonnelSequenceViewSet, basename='personnel-sequences')
router.register(r'leader-sequences', LeaderSequenceViewSet, basename='leader-sequences')
router.register(r'holidays', HolidayViewSet, basename='holidays')
router.register(r'positions', PositionViewSet, basename='positions')
router.register(r'equipments', EquipmentViewSet, basename='equipments')

urlpatterns = [
    path('', include(router.urls)),
    path('upload-image/', ImageUploadView.as_view(), name='upload-image'),
]
