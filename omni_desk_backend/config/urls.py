from django.urls import path
from .views import SystemConfigView, PageConfigListView, PageConfigDetailView

urlpatterns = [
    path('', SystemConfigView.as_view(), name='config'),
    path('pages/', PageConfigListView.as_view(), name='page-config-list'),
    path('pages/<str:page_path>/', PageConfigDetailView.as_view(), name='page-config-detail'),
]
