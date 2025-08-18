from datetime import timedelta
from rest_framework import serializers
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

CustomUser = get_user_model()

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
    
    class Meta:
        model = CustomUser
        fields = ('username', 'password', 'email')

    def validate_username(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("用户名不能为空")
        return value

    def validate(self, data):
        return data

    def create(self, validated_data):
        return CustomUser.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=validated_data.get('email', '')
        )

from django.contrib.auth import authenticate

class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    remember_me = serializers.BooleanField(default=False, required=False)

    def validate(self, data):
        user = authenticate(
            username=data.get('username'),
            password=data.get('password')
        )
        
        if not user:
            raise serializers.ValidationError("用户名或密码不正确")
            
        if not user.is_active:
            raise serializers.ValidationError("用户账户已被禁用")
            
        data['user'] = user
        return data

class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'role', 'date_joined')

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'is_active', 'is_staff', 'date_joined', 'role')
        extra_kwargs = {
            'role': {'required': True}
        }

class PersonnelSerializer(UserSerializer):
    """兼容原有人员管理接口"""
    pass

class UserAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'role', 'is_active', 'is_staff', 'date_joined')
        read_only_fields = ('id', 'username', 'email', 'is_active', 'is_staff', 'date_joined') # 除了role，其他字段不允许通过此序列化器修改

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
       data = super().validate(attrs)
       
       permissions = []
       if self.user.role == 'admin' or self.user.is_superuser:
           # 对于管理员，可以返回所有权限的特殊标记，或具体列表
           permissions = [
               'events.manage_schedule',
               'events.manage_equipment',
               'events.manage_personnel',
               'events.manage_announcements',
               'documents.view_book',  # Add permission to view books
               'documents.add_book',   # Add permission to add books
               'documents.change_book', # Add permission to change books
               'documents.delete_book' # Add permission to delete books
           ]
           print(f"Admin permissions: {permissions}") # 新增日志
       elif self.user.role == 'manager':
           permissions = [
               'events.manage_schedule',
               'events.manage_equipment',
               'events.manage_personnel',
               'events.manage_announcements',
               'documents.view_book',  # Add permission to view books
               'documents.add_book',   # Add permission to add books
               'documents.change_book', # Add permission to change books
               'documents.delete_book' # Add permission to delete books
           ]
           print(f"Manager permissions: {permissions}") # 新增日志
       
       data['permissions'] = permissions
       return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        return token
        return token
