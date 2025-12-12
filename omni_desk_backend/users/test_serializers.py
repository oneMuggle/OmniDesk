import pytest
from django.contrib.auth import get_user_model
from .serializers import UserSerializer

User = get_user_model()

@pytest.mark.django_db
def test_user_serializer_with_valid_data():
    """
    测试 UserSerializer 在提供有效数据时能够成功创建用户。
    """
    valid_data = {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'password123'
    }
    serializer = UserSerializer(data=valid_data)
    assert serializer.is_valid(), serializer.errors
    user = serializer.save()
    assert user.username == valid_data['username']
    assert user.email == valid_data['email']
    assert user.check_password(valid_data['password'])

@pytest.mark.django_db
def test_user_serializer_with_invalid_data():
    """
    测试 UserSerializer 在缺少必要字段时会验证失败。
    """
    invalid_data = {
        'username': 'testuser',
        # 缺少 email 和 password
    }
    serializer = UserSerializer(data=invalid_data)
    assert not serializer.is_valid()
    assert 'email' in serializer.errors
    assert 'password' in serializer.errors