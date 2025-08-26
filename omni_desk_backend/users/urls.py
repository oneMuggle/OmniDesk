from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CurrentUserView, UserAdminListView, UserAdminDetailView, UserProfileUpdateView, ChangePasswordView, UserPersonnelViewSet # 导入UserPersonnelViewSet

router = DefaultRouter()
router.register(r'personnel', UserPersonnelViewSet) # 为UserPersonnelViewSet注册路由

urlpatterns = [
    path('me/', CurrentUserView.as_view(), name='current-user'),  # 完整路径将是 /api/users/me/
    path('admin/', UserAdminListView.as_view(), name='user-admin-list'), # 管理员获取用户列表
    path('admin/<int:id>/', UserAdminDetailView.as_view(), name='user-admin-detail'), # 管理员修改用户
    path('me/update/', UserProfileUpdateView.as_view(), name='user-profile-update'),
    path('me/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('', include(router.urls)), # 添加路由
]
