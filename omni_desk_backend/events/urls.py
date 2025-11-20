from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TrialViewSet,
    DocumentTemplateViewSet,
    PersonnelViewSet,
    EquipmentViewSet,
    TimeSlotViewSet,
    ScheduleViewSet,
    AnnouncementViewSet,
    ImageUploadView,
    PersonnelSequenceViewSet,
    LeaderSequenceViewSet,
    PositionViewSet # Import PositionViewSet
)

router = DefaultRouter()
router.register(r'positions', PositionViewSet, basename='positions') # Register PositionViewSet
router.register(r'trials', TrialViewSet, basename='trials')
router.register(r'personnel', PersonnelViewSet, basename='personnel')
router.register(r'equipments', EquipmentViewSet, basename='equipments')
router.register(r'document-templates', DocumentTemplateViewSet, basename='document-templates')
router.register(r'time-slots', TimeSlotViewSet, basename='time-slots')
router.register(r'schedules', ScheduleViewSet, basename='schedules')
router.register(r'announcements', AnnouncementViewSet, basename='announcements')
router.register(r'personnel-sequences', PersonnelSequenceViewSet, basename='personnel-sequences')
router.register(r'leader-sequences', LeaderSequenceViewSet, basename='leader-sequences')

urlpatterns = [
    path('', include(router.urls)),
    path('upload-image/', ImageUploadView.as_view(), name='upload-image'),
]
