from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CurrentUserView
from .views import PositionViewSet, UserViewSet  # type: ignore[attr-defined]  # 历史遗留 ImportError,见 test_url_coverage.py xfail

router = DefaultRouter()
router.register(r"positions", PositionViewSet, basename="positions")  # type: ignore[attr-defined]
router.register(r"users", UserViewSet, basename="customuser")  # type: ignore[attr-defined]  # 历史遗留 ImportError,见 test_url_coverage.py xfail

urlpatterns = [
    path("me/", CurrentUserView.as_view(), name="user-me"),
    path("", include(router.urls)),
]
