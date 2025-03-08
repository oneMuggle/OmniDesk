from django.contrib import admin
from django.urls import path
from .views import CalendarEventCreateView, UserRegistrationView, UserLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/events/', CalendarEventCreateView.as_view(), name='create-event'),
    path('api/register/', UserRegistrationView.as_view(), name='register'),
    path('api/login/', UserLoginView.as_view(), name='login'),
]
