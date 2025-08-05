from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TrialViewSet,
    DocumentTemplateViewSet,
    ResponsiblePersonViewSet,
    EquipmentViewSet,
    TimeSlotViewSet,
    ScheduleViewSet,
    AnnouncementViewSet,
    ImageUploadView
)

router = DefaultRouter()
router.register(r'trials', TrialViewSet, basename='trials')
router.register(r'personnel', ResponsiblePersonViewSet, basename='personnel')
router.register(r'equipments', EquipmentViewSet, basename='equipments')
router.register(r'document-templates', DocumentTemplateViewSet, basename='document-templates')
router.register(r'responsible-persons', ResponsiblePersonViewSet, basename='responsible-persons')
router.register(r'time-slots', TimeSlotViewSet, basename='time-slots')
router.register(r'schedules', ScheduleViewSet, basename='schedules')
router.register(r'announcements', AnnouncementViewSet, basename='announcements')

urlpatterns = [
    path('', include(router.urls)),
    path('upload-image/', ImageUploadView.as_view(), name='upload-image'),
]
