from rest_framework.routers import DefaultRouter
from .views import PageVisibilityViewSet

router = DefaultRouter()
router.register(r'page-visibility', PageVisibilityViewSet, basename='page-visibility')

urlpatterns = router.urls
