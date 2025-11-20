from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'templates', views.DocumentTemplateViewSet, basename='document-template')
router.register(r'generated', views.GeneratedDocumentViewSet, basename='generated-document')
router.register(r'books', views.BookViewSet, basename='book')
router.register(r'chapters', views.ChapterViewSet, basename='chapter')
router.register(r'ebooks', views.EBookViewSet, basename='ebook')

urlpatterns = [
    path('', include(router.urls)),
    path('import_book/', views.BookImportView.as_view(), name='import-book'),
]
