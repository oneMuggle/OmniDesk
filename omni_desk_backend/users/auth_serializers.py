"""认证相关序列化器：注册、登录、JWT、密码修改、Guest 登录。"""

import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.validators import RegexValidator
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import CustomUser

CustomUser = get_user_model()


def ensure_guest_group():
    """获取或创建 Guest 组，确保其存在。"""
    group, _ = Group.objects.get_or_create(name='Guest')
    return group


class UserRegistrationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        required=True,
        min_length=4,
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9_]{4,20}$',
                message='用户名只能包含4-20位字母、数字和下划线'
            )
        ],
        error_messages={
            'blank': '用户名不能为空',
            'min_length': '用户名至少需要4个字符',
            'invalid': '用户名格式无效'
        }
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'blank': '密码不能为空'
        }
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': '请输入有效的电子邮件地址'
        }
    )
    password_confirmation = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = CustomUser
        fields = ('username', 'password', 'password_confirmation', 'email')

    def validate_username(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("用户名不能为空")
        return value

    def validate(self, data):
        if data['password'] != data['password_confirmation']:
            raise serializers.ValidationError({"password": "Passwords must match."})
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirmation', None)
        return CustomUser.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=validated_data.get('email', '')
        )


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    remember_me = serializers.BooleanField(default=False, required=False)

    def validate(self, data):
        username = data.get('username')
        password = data.get('password')

        try:
            user = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("用户名或密码不正确")

        if not user.check_password(password):
            raise serializers.ValidationError("用户名或密码不正确")

        if not user.is_active:
            raise serializers.ValidationError("用户账户已被禁用")

        data['user'] = user
        return data


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        from .serializers import get_user_permissions
        data = super().validate(attrs)
        data['permissions'] = get_user_permissions(self.user)
        return data

    @classmethod
    def get_token(cls, user):
        from .serializers import get_user_permissions
        token = super().get_token(user)
        token['username'] = user.username
        token['permissions'] = get_user_permissions(user)
        return token


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)


class GuestLoginSerializer(serializers.Serializer):
    """游客登录序列化器，创建临时游客用户并返回 JWT token。"""

    def create(self, validated_data):
        guest_group = ensure_guest_group()
        username = f"guest_{uuid.uuid4().hex[:12]}"
        password = uuid.uuid4().hex

        user = CustomUser.objects.create_user(
            username=username,
            password=password,
            is_active=True,
        )
        user.groups.add(guest_group)
        return user
