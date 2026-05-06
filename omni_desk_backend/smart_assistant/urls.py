from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SmartChatViewSet, KnowledgeBaseViewSet, SessionViewSet, AgentLogViewSet

router = DefaultRouter()
router.register(r'chat', SmartChatViewSet, basename='smart-chat')
router.register(r'knowledge-base/documents', KnowledgeBaseViewSet, basename='knowledge-docs')
router.register(r'sessions', SessionViewSet, basename='smart-sessions')
router.register(r'agent-logs', AgentLogViewSet, basename='agent-logs')

urlpatterns = [
    path('', include(router.urls)),
]
