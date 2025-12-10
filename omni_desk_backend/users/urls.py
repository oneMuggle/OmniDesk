from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CurrentUserView, UserAdminListView, UserAdminDetailView, UserProfileUpdateView, ChangePasswordView, UserPersonnelViewSet

app_name = 'users' # 定义应用命名空间

router = DefaultRouter()
router.register(r'', UserPersonnelViewSet, basename='customuser') # 指定 basename

urlpatterns = [
    path('me/profile/', UserProfileUpdateView.as_view(), name='user-profile-update'),
    path('me/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('admin/', UserAdminListView.as_view(), name='user-admin-list'),
    path('admin/<int:id>/', UserAdminDetailView.as_view(), name='user-admin-detail'),
    path('', include('users.user_urls')),
    path('', include(router.urls)),
]
