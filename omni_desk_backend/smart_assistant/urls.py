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
    AgentTaskViewSet,
)
from .views.knowledge_base import KnowledgeDatasetViewSet
from .views.doctor import DoctorView
from .views.office_download import OfficeDownloadView

router = DefaultRouter()
router.register(r"chat", SmartChatViewSet, basename="smart-chat")
router.register(r"knowledge-base/documents", KnowledgeBaseViewSet, basename="knowledge-docs")
router.register(r"knowledge-base/datasets", KnowledgeDatasetViewSet, basename="knowledge-datasets")
router.register(r"sessions", SessionViewSet, basename="smart-sessions")
router.register(r"agent-logs", AgentLogViewSet, basename="agent-logs")
router.register(r"endpoints", LlmEndpointViewSet, basename="llm-endpoints")
router.register(r"app-configs", LlmAppConfigViewSet, basename="llm-app-configs")
router.register(r"stats", StatsViewSet, basename="smart-stats")
router.register(r"tasks", AgentTaskViewSet, basename="agent-tasks")

urlpatterns = [
    # doctor 自检端点（staff 只读诊断，机器可读输出契约 format_version=1）
    path("doctor/", DoctorView.as_view(), name="smart-doctor"),
    path("office-download/<str:token>/", OfficeDownloadView.as_view(), name="office-download"),
    path("", include(router.urls)),
]
