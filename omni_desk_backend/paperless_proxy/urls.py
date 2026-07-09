from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    OutboxViewSet, HealthView, BindView, BindStatusView,
    DocumentDownloadView, DocumentPreviewView, BindingSyncStatusView,
)

router = DefaultRouter()
router.register(r'outbox', OutboxViewSet, basename='outbox')

urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
    path('bind/', BindView.as_view(), name='bind'),
    path('bind/status/', BindStatusView.as_view(), name='bind-status'),
    path('documents/<int:binding_id>/download/', DocumentDownloadView.as_view(), name='download'),
    path('documents/<int:binding_id>/preview/', DocumentPreviewView.as_view(), name='preview'),
    path('bindings/<int:binding_id>/sync-status/', BindingSyncStatusView.as_view(), name='sync-status'),
] + router.urls