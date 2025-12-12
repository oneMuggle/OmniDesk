from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import UserRegistrationView

app_name = 'users_auth' # 定义应用命名空间

urlpatterns = [
    path('registration/', UserRegistrationView.as_view(), name='auth-registration'),
    path('login/', TokenObtainPairView.as_view(), name='auth-login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]
