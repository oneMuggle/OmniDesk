from rest_framework.routers import DefaultRouter
from .views import ExperimentViewSet, DocumentTemplateViewSet, ResponsiblePersonViewSet, PersonnelViewSet, EquipmentViewSet

router = DefaultRouter()
router.register(r'experiments', ExperimentViewSet, basename='experiment')
router.register(r'templates', DocumentTemplateViewSet, basename='template')
router.register(r'responsible_persons', ResponsiblePersonViewSet, basename='responsible-person')
router.register(r'personnel', PersonnelViewSet, basename='experiment-personnel')
router.register(r'equipment', EquipmentViewSet, basename='experiment-equipment')

urlpatterns = router.urls
