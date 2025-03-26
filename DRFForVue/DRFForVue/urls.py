from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.views import UserRegistrationView, UserDetailView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Authentication endpoints
    path('api/auth/', include('users.urls')),  # 包含所有用户认证路由
    path('api/auth/register/', UserRegistrationView.as_view(), name='user-register'),  # 添加注册路由
    
    # User endpoints
    path('api/users/me/', UserDetailView.as_view(), name='user-detail'),
    
    # Events API
    path('events/', include('events.urls')),
    
    # Personnel API
    path('api/personnel/', include('users.urls')),  # 添加人员管理路由
]
