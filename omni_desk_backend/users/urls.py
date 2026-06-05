from django.urls import path

from .views import (
    ChangePasswordView,
    CurrentUserView,
    MyPersonnelView,
    UserAdminDetailView,
    UserAdminListView,
    UserPersonnelViewSet,
    UserProfileUpdateView,
    django_admin_login,
)

app_name = "users"  # 定义应用命名空间

urlpatterns = [
    path("me/profile/", UserProfileUpdateView.as_view(), name="user-profile-update"),
    path("me/personnel/", MyPersonnelView.as_view(), name="my-personnel"),
    path("me/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("control-panel/", UserAdminListView.as_view(), name="user-admin-list"),
    path("control-panel/<int:id>/", UserAdminDetailView.as_view(), name="user-admin-detail"),
    path("django-admin-login/", django_admin_login, name="django-admin-login"),
    # 为 UserPersonnelViewSet 显式定义 URL
    path("", UserPersonnelViewSet.as_view({"get": "list"}), name="user-personnel-list"),
    path(
        "<int:id>/",
        UserPersonnelViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="user-personnel-detail",
    ),
]
