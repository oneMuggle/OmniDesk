from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SmartChatViewSet,
    KnowledgeBaseViewSet,
    SessionViewSet,
    AgentLogViewSet,
    LlmEndpointViewSet,
    LlmAppConfigViewSet,
    StatsViewSet,
)

router = DefaultRouter()
router.register(r"chat", SmartChatViewSet, basename="smart-chat")
router.register(r"knowledge-base/documents", KnowledgeBaseViewSet, basename="knowledge-docs")
router.register(r"sessions", SessionViewSet, basename="smart-sessions")
router.register(r"agent-logs", AgentLogViewSet, basename="agent-logs")
router.register(r"endpoints", LlmEndpointViewSet, basename="llm-endpoints")
router.register(r"app-configs", LlmAppConfigViewSet, basename="llm-app-configs")
router.register(r"stats", StatsViewSet, basename="smart-stats")

urlpatterns = [
    path("", include(router.urls)),
]
