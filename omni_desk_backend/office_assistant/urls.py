from django.urls import path

from .views import OfficeAssistantProcessView, ProcessDocumentView

urlpatterns = [
    path("process/", OfficeAssistantProcessView.as_view(), name="office-assistant-process"),
    path("process-document/", ProcessDocumentView.as_view(), name="office-assistant-process-document"),
]
