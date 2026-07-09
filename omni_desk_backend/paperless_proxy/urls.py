from rest_framework.routers import DefaultRouter
from .views import OutboxViewSet

router = DefaultRouter()
router.register(r'outbox', OutboxViewSet, basename='outbox')

urlpatterns = router.urls