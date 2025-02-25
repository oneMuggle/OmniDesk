from django.contrib import admin
from django.urls import path
from .views import CalendarEventCreateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/events/', CalendarEventCreateView.as_view(), name='create-event'),
]
