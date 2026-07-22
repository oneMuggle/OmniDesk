from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FileProcessingViewSet

router = DefaultRouter()
# Fix-17: basename + prefix='' 让根 urls 的 path("file/", ...) 直接挂载
# URL = /api/file/{pk}/upload/ 等(测试期望)
router.register(r"", FileProcessingViewSet, basename="file")

urlpatterns = [
    path("", include(router.urls)),
]
