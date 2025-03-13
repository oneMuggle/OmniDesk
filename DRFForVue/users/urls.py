from django.urls import path
from .views import (
    UserRegistrationView,
    CustomTokenObtainPairView,
    UserProfileView
)

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user-register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
]
