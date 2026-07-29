from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    OutboxViewSet,
    OutboxRetryView,
    OutboxDiscardView,
    HealthView,
    BindView,
    BindStatusView,
    DocumentDownloadView,
    DocumentPreviewView,
    BindingSyncStatusView,
    UploadView,
    DocumentBindingViewSet,
)

router = DefaultRouter()
router.register(r"outbox", OutboxViewSet, basename="outbox")
router.register(r"documents", DocumentBindingViewSet, basename="documents")

urlpatterns = [
    path("upload/", UploadView.as_view(), name="upload"),
    path("health/", HealthView.as_view(), name="health"),
    path("bind/", BindView.as_view(), name="bind"),
    path("bind/status/", BindStatusView.as_view(), name="bind-status"),
    path("documents/<int:binding_id>/download/", DocumentDownloadView.as_view(), name="download"),
    path("documents/<int:binding_id>/preview/", DocumentPreviewView.as_view(), name="preview"),
    path("bindings/<int:binding_id>/sync-status/", BindingSyncStatusView.as_view(), name="sync-status"),
    # P0-H:管理面显式端点(置于 router.urls 之前,优先于 ViewSet retry action)
    path("outbox/<int:pk>/retry/", OutboxRetryView.as_view(), name="outbox-retry"),
    path("outbox/<int:pk>/discard/", OutboxDiscardView.as_view(), name="outbox-discard"),
] + router.urls
