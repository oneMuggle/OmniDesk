from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.views import RegisterView, UserDetailView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Authentication endpoints
    path('api/auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    
    # User endpoints
    path('api/users/me/', UserDetailView.as_view(), name='user-detail'),
    
    # Events API
    path('api/events/', include('events.urls')),
]
