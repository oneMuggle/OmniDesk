from django.urls import path
from .views import SystemConfigView

urlpatterns = [
    path('', SystemConfigView.as_view(), name='config'),
]
