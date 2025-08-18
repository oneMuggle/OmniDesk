from django.urls import path
from .views import CurrentUserView, UserAdminListView, UserAdminDetailView # 导入 UserAdminListView, UserAdminDetailView

urlpatterns = [
    path('me/', CurrentUserView.as_view(), name='current-user'),  # 完整路径将是 /api/users/me/
    path('admin/', UserAdminListView.as_view(), name='user-admin-list'), # 管理员获取用户列表
    path('admin/<int:pk>/', UserAdminDetailView.as_view(), name='user-admin-detail'), # 管理员修改用户
]
