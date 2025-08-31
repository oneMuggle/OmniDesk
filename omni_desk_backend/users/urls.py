from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CurrentUserView, UserAdminListView, UserAdminDetailView, UserProfileUpdateView, ChangePasswordView, UserPersonnelViewSet

router = DefaultRouter()
router.register(r'personnel', UserPersonnelViewSet)

urlpatterns = [
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('admin/', UserAdminListView.as_view(), name='user-admin-list'),
    path('admin/<int:id>/', UserAdminDetailView.as_view(), name='user-admin-detail'),
    path('me/update/', UserProfileUpdateView.as_view(), name='user-profile-update'),
    path('me/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('', UserPersonnelViewSet.as_view({'get': 'list'}), name='user-list'), # 将 /api/users/ 路由指向 UserPersonnelViewSet 的列表操作
]

urlpatterns += router.urls # 将 router 生成的 URL 添加到 urlpatterns 列表末尾
