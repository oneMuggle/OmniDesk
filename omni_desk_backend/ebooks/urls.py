from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EbookViewSet

router = DefaultRouter()
router.register(r'ebooks', EbookViewSet, basename='ebook')

urlpatterns = [
    path('', include(router.urls)),
]
