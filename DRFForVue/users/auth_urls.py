from django.urls import path
from .views import UserRegistrationView, CustomTokenObtainPairView

urlpatterns = [
    path('registration/', UserRegistrationView.as_view(), name='auth-registration'),
    path('login/', CustomTokenObtainPairView.as_view(), name='auth-login'),
]
