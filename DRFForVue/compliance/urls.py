from rest_framework.routers import DefaultRouter
from .views import ComplianceIssueViewSet

router = DefaultRouter()
router.register(r'', ComplianceIssueViewSet)

urlpatterns = router.urls