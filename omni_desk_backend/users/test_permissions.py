import pytest
from unittest.mock import Mock
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from users.permissions import HasPermission

@pytest.mark.django_db
class TestHasPermission:
    @pytest.fixture
    def content_type(self, db):
        return ContentType.objects.create(app_label='test_app', model='test_model')

    @pytest.fixture
    def user_with_permission(self, db, content_type):
        user = User.objects.create_user(username='testuser_with_perm', password='password')
        permission = Permission.objects.create(
            codename='test_permission',
            name='Test Permission',
            content_type=content_type,
        )
        user.user_permissions.add(permission)
        return user

    @pytest.fixture
    def user_without_permission(self, db):
        return User.objects.create_user(username='testuser_without_perm', password='password')

    def test_has_permission_returns_true_for_user_with_permission(self, user_with_permission):
        """
        测试拥有所需权限的用户 has_permission 返回 True。
        """
        permission_checker = HasPermission()
        request = Mock()
        request.user = user_with_permission
        view = Mock()
        view.required_permission = 'test_app.test_permission'
        
        assert permission_checker.has_permission(request, view) is True

    def test_has_permission_returns_false_for_user_without_permission(self, user_without_permission, content_type):
        """
        测试没有所需权限的用户 has_permission 返回 False。
        """
        permission_checker = HasPermission()
        request = Mock()
        request.user = user_without_permission
        view = Mock()
        view.required_permission = 'test_app.test_permission'
        
        # 确保权限存在，以便检查
        Permission.objects.get_or_create(
            codename='test_permission',
            name='Test Permission',
            content_type=content_type,
        )

        assert permission_checker.has_permission(request, view) is False

    def test_has_permission_returns_true_when_no_permission_is_required(self, user_without_permission):
        """
        测试当视图不需要任何特定权限时 has_permission 返回 True。
        """
        permission_checker = HasPermission()
        request = Mock()
        request.user = user_without_permission
        view = Mock()
        # 模拟一个没有 'required_permission' 属性的视图
        if hasattr(view, 'required_permission'):
            del view.required_permission
        
        assert permission_checker.has_permission(request, view) is True