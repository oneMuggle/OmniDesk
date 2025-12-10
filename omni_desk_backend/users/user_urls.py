from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import CurrentUserView, PositionViewSet

router = DefaultRouter()
router.register(r'positions', PositionViewSet, basename='positions')

urlpatterns = [
    path('me/', CurrentUserView.as_view(), name='user-me'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('', include(router.urls)),
]
