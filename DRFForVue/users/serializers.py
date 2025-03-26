from rest_framework import serializers
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

CustomUser = get_user_model()

class UserRegisterSerializer(serializers.ModelSerializer):
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
        min_length=6,
        style={'input_type': 'password'},
        error_messages={
            'blank': '密码不能为空',
            'min_length': '密码至少需要6个字符'
        }
    )
    password_confirmation = serializers.CharField(
        write_only=True,
        required=True,
        min_length=6,
        style={'input_type': 'password'},
        error_messages={
            'blank': '请确认密码',
            'min_length': '确认密码至少需要6个字符'
        }
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        error_messages={
            'invalid': '请输入有效的电子邮件地址'
        }
    )
    
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
            raise serializers.ValidationError({
                "password": ["两次输入的密码不一致"],
                "password_confirmation": ["两次输入的密码不一致"],
                "non_field_errors": ["密码和确认密码不匹配"]
            })
        return data

    def create(self, validated_data):
        try:
            return CustomUser.objects.create_user(
                username=validated_data['username'],
                password=validated_data['password'],
                email=validated_data.get('email', '')
            )
        except Exception as e:
            # 捕获并记录详细的数据库错误
            from django.db import IntegrityError
            if isinstance(e, IntegrityError):
                raise serializers.ValidationError({"email": "该邮箱已被注册"})
            raise e

class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'date_joined')

class PersonnelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'name', 'is_active', 'is_staff', 'date_joined')

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        return token
