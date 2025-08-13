from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MemoViewSet

router = DefaultRouter()
router.register(r'', MemoViewSet, basename='memo')

urlpatterns = [
    path('', include(router.urls)),
]