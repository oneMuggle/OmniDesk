# omni_desk_backend/search_federation/urls.py
from django.urls import path
from .views import UnifiedSearchView

urlpatterns = [
    path("unified/", UnifiedSearchView.as_view(), name="unified"),
]
