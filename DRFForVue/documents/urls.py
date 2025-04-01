from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'templates', views.DocumentTemplateViewSet, basename='document-template')
router.register(r'generated', views.GeneratedDocumentViewSet, basename='generated-document')

urlpatterns = [
    path('', include(router.urls)),
    path('<int:template_id>/generate/', views.GeneratedDocumentViewSet.as_view({'post': 'create'}), name='generate-document'),
]
