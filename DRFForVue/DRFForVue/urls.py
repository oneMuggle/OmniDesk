from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.views import UserRegistrationView, UserDetailView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Authentication endpoints
    # Authentication & User endpoints
    path('api/', include([
        path('users/', include('users.urls')),     # 用户个人资料路由
        path('auth/', include('users.auth_urls')), # 认证路由
        path('events/', include('events.urls')),  # 事件相关路由
        path('documents/', include('documents.urls')),  # 新增文档相关路由
        path('config/', include('config.urls')),  # 配置相关路由
        path('memos/', include('memos.urls')),     # 备忘录相关路由
        path('dify-apps/', include('dify_apps.urls')), # Dify 应用相关路由
        path('office_assistant/', include('office_assistant.urls')), # Office助手相关路由
        path('projects/', include('projects.urls')), # 项目管理相关路由
        path('compliance/', include('compliance.urls')), # 合规问题管理相关路由
    ])),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
