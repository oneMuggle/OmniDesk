from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import ExternalLinkViewSet, IntegrationServiceViewSet

router = DefaultRouter()
router.register(r'external-links', ExternalLinkViewSet, basename='external-link')
router.register(r'integrations', IntegrationServiceViewSet, basename='integration-service')

urlpatterns = [
    path('', include(router.urls)),
]
