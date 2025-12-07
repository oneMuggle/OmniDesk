from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GroupViewSet, PageRouteViewSet, GroupPermissionView, UserPermissionView, GroupedPermissionsView

router = DefaultRouter()
router.register(r'groups', GroupViewSet)
router.register(r'pages', PageRouteViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('groups/<int:group_id>/permissions/', GroupPermissionView.as_view(), name='group-permissions'),
    path('users/me/permissions/', UserPermissionView.as_view(), name='user-permissions'),
    path('permissions/grouped/', GroupedPermissionsView.as_view(), name='grouped-permissions'),
]