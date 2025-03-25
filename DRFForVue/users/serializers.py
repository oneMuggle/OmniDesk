from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

CustomUser = get_user_model()

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={'blank': '密码不能为空'}
    )
    
    class Meta:
        model = CustomUser
        fields = ('username', 'password')

    def create(self, validated_data):
        try:
            return CustomUser.objects.create_user(
                username=validated_data['username'],
                password=validated_data['password']
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

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        return token
