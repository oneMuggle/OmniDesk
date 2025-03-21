from rest_framework.routers import DefaultRouter
from .views import EventViewSet, DocumentTemplateViewSet

router = DefaultRouter()
router.register(r'events', EventViewSet, basename='event')
router.register(r'templates', DocumentTemplateViewSet, basename='template')

urlpatterns = router.urls
