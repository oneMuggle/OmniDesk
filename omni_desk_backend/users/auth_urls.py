from django.urls import path
from .views import UserRegistrationView, UserLoginView

app_name = 'users_auth' # 定义应用命名空间

urlpatterns = [
    path('registration/', UserRegistrationView.as_view(), name='auth-registration'),
    path('login/', UserLoginView.as_view(), name='auth-login'),
]
