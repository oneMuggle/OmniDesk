from django.urls import path
from .views import (
    RegisterView,
    CustomTokenObtainPairView,
    UserDetailView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('profile/', UserDetailView.as_view(), name='user-profile'),
]
