from rest_framework.routers import DefaultRouter
from .views import TrialViewSet, DocumentTemplateViewSet, ResponsiblePersonViewSet, EquipmentViewSet, TimeSlotViewSet

router = DefaultRouter()
router.register(r'trials', TrialViewSet, basename='trials')
router.register(r'personnel', ResponsiblePersonViewSet, basename='personnel')
router.register(r'equipments', EquipmentViewSet, basename='equipments')
router.register(r'document-templates', DocumentTemplateViewSet, basename='document-templates')
router.register(r'responsible-persons', ResponsiblePersonViewSet, basename='responsible-persons')
router.register(r'time-slots', TimeSlotViewSet, basename='time-slots')

urlpatterns = router.urls
