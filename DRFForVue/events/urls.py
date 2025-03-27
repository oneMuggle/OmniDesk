from rest_framework.routers import DefaultRouter
from .views import EventViewSet, DocumentTemplateViewSet, ResponsiblePersonViewSet, PersonnelViewSet

router = DefaultRouter()
router.register(r'events', EventViewSet, basename='event')
router.register(r'templates', DocumentTemplateViewSet, basename='template')
router.register(r'responsible_persons', ResponsiblePersonViewSet, basename='responsible-person')
router.register(r'personnel', PersonnelViewSet, basename='personnel')

urlpatterns = router.urls
