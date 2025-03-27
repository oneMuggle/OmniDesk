from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.views import UserRegistrationView, UserDetailView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Authentication endpoints
    # Authentication & User endpoints
    path('api/auth/', include('users.urls')), 
    
    # Events API
    path('events/', include('events.urls')),
]
