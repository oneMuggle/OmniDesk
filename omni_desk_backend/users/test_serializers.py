import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework_simplejwt.tokens import AccessToken
from .serializers import UserSerializer, CustomTokenObtainPairSerializer

User = get_user_model()

@pytest.mark.django_db
def test_user_serializer_with_valid_data():
    """
    测试 UserSerializer 在提供有效数据时能够成功创建用户。
    """
    valid_data = {
        'username': 'testuser',
        'email': 'test@example.com',
    }
    serializer = UserSerializer(data=valid_data)
    assert serializer.is_valid(), serializer.errors
    user = User.objects.create(**valid_data)
    assert user.username == valid_data['username']
    assert user.email == valid_data['email']

@pytest.mark.django_db
def test_user_serializer_with_invalid_data():
    """
    测试 UserSerializer 在缺少必要字段时会验证失败。
    """
    invalid_data = {
        'username': '',
    }
    serializer = UserSerializer(data=invalid_data)
    assert not serializer.is_valid()
    assert 'username' in serializer.errors


@pytest.mark.django_db
class TestCustomTokenObtainPairSerializer:
    def test_get_token_includes_permissions(self):
        """
        测试登录响应中包含了正确的用户权限。
        """
        # 1. 创建用户和权限
        user = User.objects.create_user(username='testpermuser', password='password123')
        content_type = ContentType.objects.create(app_label='test_app', model='test_model')
        permission = Permission.objects.create(
            codename='can_do_something',
            name='Can do something',
            content_type=content_type,
        )
        user.user_permissions.add(permission)

        # 2. 模拟登录并获取令牌
        serializer = CustomTokenObtainPairSerializer(data={
            'username': 'testpermuser',
            'password': 'password123',
        })
        assert serializer.is_valid(), serializer.errors
        tokens = serializer.validated_data

        # 3. 验证响应数据中包含权限（permissions 在 validate() 返回的 data 中，不在 JWT payload 中）
        expected_permission = f'{content_type.app_label}.{permission.codename}'
        permissions = tokens.get('permissions', [])
        assert expected_permission in permissions
        assert len(permissions) == 1

        # 4. 也验证 JWT token 可以正常解码
        access_token = AccessToken(tokens['access'])
        assert access_token.get('username') == 'testpermuser'
