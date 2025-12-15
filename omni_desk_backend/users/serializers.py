from datetime import timedelta
from rest_framework import serializers
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from personnel.models import Personnel, Position
from personnel.serializers import PersonnelSerializer
from .models import PhoneNumber
from permissions.models import GroupPagePermission

CustomUser = get_user_model()

def get_user_permissions(user):
    """
    获取用户的所有权限，包括标准的Django权限和自定义页面权限。
    """
    permissions = set(user.get_all_permissions())
    if user.is_staff or user.is_superuser:
        permissions.add('admin')
    
    # 获取用户通过组获得的页面路由权限
    user_groups = user.groups.all()
    group_names = set(user_groups.values_list('name', flat=True))
    page_permissions = GroupPagePermission.objects.filter(group__in=user_groups).select_related('page').values_list('page__path', flat=True)
    permissions.update(page_permissions)

    if 'Admin' in group_names:
        permissions.add('events.manage_schedule')
        permissions.add('documents.view_book')

    if 'Manager' in group_names:
        permissions.add('manager')
        permissions.add('events.manage_personnel')
        
    return list(permissions)

class PhoneNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhoneNumber
        fields = ['id', 'number']

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
        # 移除 password_confirmation，因为它不是模型字段
        validated_data.pop('password_confirmation', None)
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

class UserDetailSerializer(serializers.ModelSerializer):
    phone_numbers = PhoneNumberSerializer(many=True, required=False)
    assigned_by = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        allow_null=True,
        required=False
    )
    assigned_by_username = serializers.CharField(source='assigned_by.username', read_only=True)
    personnel = serializers.StringRelatedField(read_only=True)
    personnel_id = serializers.PrimaryKeyRelatedField(
        queryset=Personnel.objects.all(),
        source='personnel',
        allow_null=True,
        required=False,
        write_only=True
    )
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'real_name', 'avatar', 'date_joined', 'assigned_by', 'assigned_by_username', 'personnel', 'personnel_id', 'phone_numbers', 'permissions')
        read_only_fields = ()
        extra_kwargs = {}

    def get_permissions(self, obj):
        return get_user_permissions(obj)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.personnel:
            self.fields['real_name'].read_only = True
    
    def update(self, instance, validated_data):
        phone_numbers_data = validated_data.pop('phone_numbers', None)
        
        # Update user instance using the default update logic
        instance = super().update(instance, validated_data)

        if phone_numbers_data is not None:
            # Clear existing phone numbers
            instance.phone_numbers.all().delete()
            # Add new phone numbers
            for phone_number_data in phone_numbers_data:
                PhoneNumber.objects.create(user=instance, **phone_number_data)

        return instance

class UserSerializer(serializers.ModelSerializer):
    phone_numbers = PhoneNumberSerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'real_name', 'is_active', 'is_staff', 'date_joined', 'personnel', 'personnel_id', 'phone_numbers', 'permissions')
        extra_kwargs = {
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.personnel:
            self.fields['real_name'].read_only = True

    def get_permissions(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return {'can_change': False, 'can_delete': False}

        user = request.user
        return {
            'can_change': user.has_perm('users.change_customuser', obj),
            'can_delete': user.has_perm('users.delete_customuser', obj)
        }
    personnel = serializers.StringRelatedField(read_only=True)
    personnel_id = serializers.PrimaryKeyRelatedField(
        queryset=Personnel.objects.all(),
        source='personnel',
        allow_null=True,
        required=False,
        write_only=True
    )


class UserAdminSerializer(serializers.ModelSerializer):
    personnel = PersonnelSerializer(read_only=True)
    personnel_id = serializers.PrimaryKeyRelatedField(
        queryset=Personnel.objects.all(),
        source='personnel',
        allow_null=True,
        required=False # 确保在更新时不是必需的
    )
    phone_numbers = PhoneNumberSerializer(many=True, required=False)
    groups = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), many=True, required=False)

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'is_active', 'is_staff', 'date_joined', 'personnel', 'personnel_id', 'real_name', 'avatar', 'phone_numbers', 'groups')
        read_only_fields = ('id', 'email', 'is_active', 'is_staff', 'date_joined', 'avatar')

    def create(self, validated_data):
        phone_numbers_data = validated_data.pop('phone_numbers', [])
        user = CustomUser.objects.create_user(**validated_data)
        for phone_number_data in phone_numbers_data:
            PhoneNumber.objects.create(user=user, **phone_number_data)
        return user

    def update(self, instance, validated_data):
        phone_numbers_data = validated_data.pop('phone_numbers', None)
        groups_data = validated_data.pop('groups', None)

        # Update user instance
        instance.username = validated_data.get('username', instance.username)
        instance.real_name = validated_data.get('real_name', instance.real_name)
        instance.personnel = validated_data.get('personnel', instance.personnel)
        
        if groups_data is not None:
            instance.groups.set(groups_data)

        instance.save()

        if phone_numbers_data is not None:
            # Clear existing phone numbers
            instance.phone_numbers.all().delete()
            # Add new phone numbers
            for phone_number_data in phone_numbers_data:
                PhoneNumber.objects.create(user=instance, **phone_number_data)

        return instance

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        # 获取用户的所有权限（包括直接分配和从组继承的），并将其添加到响应中。
        # 权限格式为 'app_label.codename'。
        data['permissions'] = get_user_permissions(self.user)
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        # Add dynamic permissions and roles to the JWT token payload.
        token['permissions'] = get_user_permissions(user)
        return token

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

class UserPersonnelSerializer(serializers.ModelSerializer):
    personnel = PersonnelSerializer(read_only=True)
    personnel_id = serializers.PrimaryKeyRelatedField(
        queryset=Personnel.objects.all(),
        source='personnel',
        allow_null=True,
        required=False,
        write_only=True
    )

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'real_name', 'personnel', 'personnel_id')
        read_only_fields = ('username',)


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = '__all__'
