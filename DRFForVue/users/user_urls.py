from django.urls import path
from rest_framework.permissions import IsAuthenticated
from .views import UserDetailView

urlpatterns = [
    path('me/', UserDetailView.as_view(
        permission_classes=[IsAuthenticated]
    ), name='user-me'),
]
