from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import CurrentUserView, PositionViewSet, UserPersonnelViewSet

router = DefaultRouter()
router.register(r'positions', PositionViewSet, basename='positions')
router.register(r'users', UserPersonnelViewSet, basename='customuser')

urlpatterns = [
    path('me/', CurrentUserView.as_view(), name='user-me'),
    path('', include(router.urls)),
]
