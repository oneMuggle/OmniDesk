from django.urls import path
from .views import CurrentUserView, UserAdminListView, UserAdminDetailView, UserProfileUpdateView, ChangePasswordView

urlpatterns = [
    path('me/', CurrentUserView.as_view(), name='current-user'),  # 完整路径将是 /api/users/me/
    path('admin/', UserAdminListView.as_view(), name='user-admin-list'), # 管理员获取用户列表
    path('admin/<int:id>/', UserAdminDetailView.as_view(), name='user-admin-detail'), # 管理员修改用户
    path('me/update/', UserProfileUpdateView.as_view(), name='user-profile-update'),
    path('me/change-password/', ChangePasswordView.as_view(), name='change-password'),
]
