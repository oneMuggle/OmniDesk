from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import OutboxViewSet, HealthView, BindView, BindStatusView

router = DefaultRouter()
router.register(r'outbox', OutboxViewSet, basename='outbox')

urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
    path('bind/', BindView.as_view(), name='bind'),
    path('bind/status/', BindStatusView.as_view(), name='bind-status'),
] + router.urls