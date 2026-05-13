"""用户相关序列化器：用户详情、列表、管理、Personnel 关联。"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

from personnel.models import Personnel
from personnel.serializers import PersonnelSerializer

from .models import CustomUser, PhoneNumber
from .serializers import get_user_permissions

CustomUser = get_user_model()


class PhoneNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhoneNumber
        fields = ['id', 'number']


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
        instance = super().update(instance, validated_data)

        if phone_numbers_data is not None:
            instance.phone_numbers.all().delete()
            for phone_number_data in phone_numbers_data:
                PhoneNumber.objects.create(user=instance, **phone_number_data)

        return instance


class UserSerializer(serializers.ModelSerializer):
    phone_numbers = PhoneNumberSerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'real_name', 'is_active', 'is_staff', 'date_joined', 'personnel', 'personnel_id', 'phone_numbers', 'permissions')
        extra_kwargs = {}

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
        required=False
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

        instance.username = validated_data.get('username', instance.username)
        instance.real_name = validated_data.get('real_name', instance.real_name)
        instance.personnel = validated_data.get('personnel', instance.personnel)

        if groups_data is not None:
            instance.groups.set(groups_data)

        instance.save()

        if phone_numbers_data is not None:
            instance.phone_numbers.all().delete()
            for phone_number_data in phone_numbers_data:
                PhoneNumber.objects.create(user=instance, **phone_number_data)

        return instance


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
