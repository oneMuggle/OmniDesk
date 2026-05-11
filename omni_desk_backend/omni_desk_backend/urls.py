from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from config.views import ollama_configs_view
from omni_desk_backend.health import health_check
from sensor_management.views import SensorCategoryViewSet, StorageLocationViewSet

router = DefaultRouter()
router.register(r'categories', SensorCategoryViewSet, basename='sensor-category')
router.register(r'storage-locations', StorageLocationViewSet, basename='storage-location')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health-check'),
    # Authentication endpoints
    # Authentication & User endpoints
    path('api/', include([
        path('', include(router.urls)),
        path('sensor-management/', include('sensor_management.urls')),
        path('ollama/configs/', ollama_configs_view, name='ollama-configs-simple'),
        path('users/', include('users.urls')),     # 用户个人资料路由
        path('auth/', include('users.auth_urls', namespace='users_auth')), # 认证路由
        path('events/', include('events.urls')),  # 事件相关路由
        path('documents/', include('documents.urls')),  # 新增文档相关路由
        path('config/', include('config.urls')),  # 配置相关路由
        path('memos/', include('memos.urls')),     # 备忘录相关路由
        path('dify-apps/', include('dify_apps.urls')), # Dify 应用相关路由
        path('office_assistant/', include('office_assistant.urls')), # Office助手相关路由
        path('projects/', include('projects.urls')), # 项目管理相关路由
        path('compliance/', include('compliance.urls')), # 合规问题管理相关路由
        path('ragflow-service/', include('ragflow_service.urls')), # Ragflow 服务相关路由
        path('meeting-rooms/', include('meeting_rooms.urls')), # 会议室预约相关路由
        path('permissions/', include('permissions.urls')), # 权限管理相关路由
        path('personnel/', include('personnel.urls')), # 人事管理相关路由
        path('communication/', include('communication.urls')), # 用户交流相关路由
        path('', include('news.urls')), # 新闻发布相关路由
        path('sensors/', include('sensors.urls')), # 传感器管理相关路由
        path('', include('ebooks.urls')), # 电子书管理相关路由
        path('smart-assistant/', include('smart_assistant.urls')), # 智能助手相关路由
        path('notifications/', include('notifications.urls')), # 通知中心相关路由
        path('dashboard/', include('dashboard.urls')), # 仪表盘数据接口
        path('system/', include('core.urls')), # 系统信息（版本等）
    ])),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
