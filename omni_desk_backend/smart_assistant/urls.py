from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SmartChatViewSet, KnowledgeBaseViewSet

router = DefaultRouter()
router.register(r'chat', SmartChatViewSet, basename='smart-chat')
router.register(r'knowledge-base/documents', KnowledgeBaseViewSet, basename='knowledge-docs')

urlpatterns = [
    path('', include(router.urls)),
]
