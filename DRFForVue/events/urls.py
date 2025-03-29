from rest_framework.routers import DefaultRouter
from .views import ExperimentViewSet, DocumentTemplateViewSet, ResponsiblePersonViewSet, EquipmentViewSet

router = DefaultRouter()
router.register(r'experiments', ExperimentViewSet, basename='experiments')
router.register(r'personnel', ResponsiblePersonViewSet, basename='personnel')
router.register(r'equipments', EquipmentViewSet, basename='equipments')
router.register(r'document-templates', DocumentTemplateViewSet, basename='document-templates')
router.register(r'responsible-persons', ResponsiblePersonViewSet, basename='responsible-persons')

urlpatterns = router.urls
