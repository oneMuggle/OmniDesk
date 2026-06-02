from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import ExternalLinkViewSet, IntegrationServiceViewSet, PluginViewSet, PluginTemplateView

router = DefaultRouter()
router.register(r"external-links", ExternalLinkViewSet, basename="external-link")
router.register(r"integrations", IntegrationServiceViewSet, basename="integration-service")
router.register(r"plugins", PluginViewSet, basename="plugin")
router.register(r"plugin-templates", PluginTemplateView, basename="plugin-template")

urlpatterns = [
    path("", include(router.urls)),
]
