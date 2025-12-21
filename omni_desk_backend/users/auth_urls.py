from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import UserRegistrationView, UserLoginView

app_name = 'users_auth' # 定义应用命名空间

urlpatterns = [
    path('registration/', UserRegistrationView.as_view(), name='auth-registration'),
    path('login/', UserLoginView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
]
