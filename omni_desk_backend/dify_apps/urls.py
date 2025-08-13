from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DifyAppViewSet

router = DefaultRouter()
router.register(r'', DifyAppViewSet)

urlpatterns = [
    path('', include(router.urls)),
]