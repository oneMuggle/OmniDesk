from django.urls import path
from .views import OfficeAssistantProcessView

urlpatterns = [
    path('process/', OfficeAssistantProcessView.as_view(), name='office-assistant-process'),
]