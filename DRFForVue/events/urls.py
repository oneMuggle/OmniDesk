from rest_framework.routers import DefaultRouter
from .views import EventViewSet, DocumentTemplateViewSet, ResponsiblePersonViewSet, PersonnelViewSet, EquipmentViewSet

router = DefaultRouter()
router.register(r'events', EventViewSet, basename='event')
router.register(r'templates', DocumentTemplateViewSet, basename='template')
router.register(r'responsible_persons', ResponsiblePersonViewSet, basename='responsible-person')
router.register(r'personnel', PersonnelViewSet, basename='personnel')
router.register(r'equipment', EquipmentViewSet, basename='equipment')

urlpatterns = router.urls
