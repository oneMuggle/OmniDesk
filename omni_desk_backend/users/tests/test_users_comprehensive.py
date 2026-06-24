"""users 模块综合测试：权限缓存、序列化器、guest 登录、密码修改等。"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from rest_framework import serializers

from permissions.models import GroupPagePermission, PageRoute

CustomUser = get_user_model()


# ==================== get_user_permissions 测试 ====================

@pytest.mark.django_db
class TestGetUserPermissions:
    def test_superuser_gets_admin_permission(self):
        """superuser 应自动获得 admin 权限"""
        from users.serializers import get_user_permissions
        user = CustomUser.objects.create_superuser(
            username='super', email='super@test.com', password='pass123'
        )
        perms = get_user_permissions(user)
        assert 'admin' in perms

    def test_staff_gets_admin_permission(self):
        """staff 用户应自动获得 admin 权限"""
        from users.serializers import get_user_permissions
        user = CustomUser.objects.create_user(
            username='staff', email='staff@test.com', password='pass123', is_staff=True
        )
        perms = get_user_permissions(user)
        assert 'admin' in perms

    def test_regular_user_no_admin(self):
        """普通用户不应获得 admin 权限"""
        from users.serializers import get_user_permissions
        user = CustomUser.objects.create_user(
            username='regular', email='r@test.com', password='pass123'
        )
        perms = get_user_permissions(user)
        assert 'admin' not in perms

    def test_admin_group_gets_special_permissions(self):
        """Admin 组用户应获得 events.manage_schedule 和 documents.view_book"""
        from users.serializers import get_user_permissions
        admin_group = Group.objects.create(name='Admin')
        user = CustomUser.objects.create_user(
            username='admin_member', email='a@test.com', password='pass123'
        )
        user.groups.add(admin_group)
        perms = get_user_permissions(user)
        assert 'events.manage_schedule' in perms
        assert 'documents.view_book' in perms

    def test_manager_group_gets_manager_permission(self):
        """Manager 组用户应获得 manager 和 events.manage_personnel 权限"""
        from users.serializers import get_user_permissions
        manager_group = Group.objects.create(name='Manager')
        user = CustomUser.objects.create_user(
            username='manager_member', email='m@test.com', password='pass123'
        )
        user.groups.add(manager_group)
        perms = get_user_permissions(user)
        assert 'manager' in perms
        assert 'events.manage_personnel' in perms

    def test_group_page_permissions_cached(self):
        """组页面权限应被缓存"""
        from users.serializers import get_user_permissions, _get_group_page_permissions
        group = Group.objects.create(name='TestGroup')
        page = PageRoute.objects.create(path='/test', name='测试页面')
        GroupPagePermission.objects.create(group=group, page=page)
        user = CustomUser.objects.create_user(
            username='grp_user', email='g@test.com', password='pass123'
        )
        user.groups.add(group)

        # 第一次调用（未缓存）
        perms1 = get_user_permissions(user)
        assert '/test' in perms1

        # 删除直接权限缓存，但组权限缓存应还在
        cache.delete(f'user_permissions_{user.pk}')
        perms2 = get_user_permissions(user)
        assert '/test' in perms2

    def test_clear_user_permissions_cache_for_user(self):
        """清除单个用户权限缓存"""
        from users.serializers import get_user_permissions, clear_user_permissions_cache
        user = CustomUser.objects.create_user(
            username='cache_user', email='c@test.com', password='pass123'
        )
        get_user_permissions(user)  # 写入缓存
        clear_user_permissions_cache(user)
        cached = cache.get(f'user_permissions_{user.pk}')
        assert cached is None

    @pytest.mark.xfail(reason="LocMemCache does not support iter_keys")
    def test_clear_user_permissions_cache_for_all(self):
        """清除所有用户权限缓存"""
        from users.serializers import get_user_permissions, clear_user_permissions_cache
        user1 = CustomUser.objects.create_user(username='all_1', email='a1@test.com', password='pass123')
        user2 = CustomUser.objects.create_user(username='all_2', email='a2@test.com', password='pass123')
        get_user_permissions(user1)
        get_user_permissions(user2)
        clear_user_permissions_cache()
        assert cache.get(f'user_permissions_{user1.pk}') is None
        assert cache.get(f'user_permissions_{user2.pk}') is None


# ==================== _get_group_page_permissions 测试 ====================

@pytest.mark.django_db
class TestGroupPagePermissions:
    def test_returns_page_paths(self):
        """应返回组的页面路径集合"""
        from users.serializers import _get_group_page_permissions
        group = Group.objects.create(name='PathGroup')
        page1 = PageRoute.objects.create(path='/page1', name='页面1')
        page2 = PageRoute.objects.create(path='/page2', name='页面2')
        GroupPagePermission.objects.create(group=group, page=page1)
        GroupPagePermission.objects.create(group=group, page=page2)

        perms = _get_group_page_permissions(group.id)
        assert '/page1' in perms
        assert '/page2' in perms

    def test_empty_group_returns_empty_set(self):
        """没有页面权限的组应返回空集合"""
        from users.serializers import _get_group_page_permissions
        group = Group.objects.create(name='EmptyGroup')
        perms = _get_group_page_permissions(group.id)
        assert perms == set()

    def test_caching_works(self):
        """组权限应被缓存"""
        from users.serializers import _get_group_page_permissions
        group = Group.objects.create(name='CacheGroup')
        page = PageRoute.objects.create(path='/cached', name='缓存页面')
        GroupPagePermission.objects.create(group=group, page=page)

        perms1 = _get_group_page_permissions(group.id)
        # 删除数据库记录，缓存应仍返回旧值
        GroupPagePermission.objects.all().delete()
        perms2 = _get_group_page_permissions(group.id)
        assert '/cached' in perms2


# ==================== UserRegistrationSerializer 测试 ====================

@pytest.mark.django_db
class TestUserRegistrationSerializer:
    def test_valid_registration(self):
        """有效注册应成功创建用户"""
        from users.auth_serializers import UserRegistrationSerializer
        data = {
            'username': 'newuser',
            'password': 'SecurePass123',
            'password_confirmation': 'SecurePass123',
            'email': 'newuser@example.com',
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()
        assert user.username == 'newuser'
        assert user.email == 'newuser@example.com'
        assert user.check_password('SecurePass123')

    def test_password_mismatch(self):
        """密码不匹配应验证失败"""
        from users.auth_serializers import UserRegistrationSerializer
        data = {
            'username': 'baduser',
            'password': 'Pass123',
            'password_confirmation': 'Different456',
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert 'password' in serializer.errors or 'non_field_errors' in serializer.errors

    def test_invalid_username_format(self):
        """无效的用户名格式应验证失败"""
        from users.auth_serializers import UserRegistrationSerializer
        data = {
            'username': 'ab',  # 太短
            'password': 'Pass123',
            'password_confirmation': 'Pass123',
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()

    def test_username_with_special_chars(self):
        """用户名包含特殊字符应验证失败"""
        from users.auth_serializers import UserRegistrationSerializer
        data = {
            'username': 'user@name!',
            'password': 'Pass123',
            'password_confirmation': 'Pass123',
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()

    def test_duplicate_username(self):
        """重复用户名应在 is_valid 阶段被检测（避免 DB IntegrityError）"""
        from users.auth_serializers import UserRegistrationSerializer
        CustomUser.objects.create_user(username='existing', password='pass123')
        data = {
            'username': 'existing',
            'password': 'NewPass123',
            'password_confirmation': 'NewPass123',
        }
        serializer = UserRegistrationSerializer(data=data)
        # 修复后:validate_username 提前查 DB,is_valid() 阶段就返回 False
        assert not serializer.is_valid()
        assert 'username' in serializer.errors
        assert '用户名已被使用' in str(serializer.errors['username'])

    def test_email_optional(self):
        """email 应为可选字段"""
        from users.auth_serializers import UserRegistrationSerializer
        data = {
            'username': 'noemailuser',
            'password': 'Pass123',
            'password_confirmation': 'Pass123',
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()
        assert user.email == ''

    def test_username_stripped_whitespace(self):
        """用户名前后空格应被去除"""
        from users.auth_serializers import UserRegistrationSerializer
        data = {
            'username': '  trimmeduser  ',
            'password': 'Pass123',
            'password_confirmation': 'Pass123',
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()
        assert user.username == 'trimmeduser'


# ==================== ChangePasswordSerializer 测试 ====================

@pytest.mark.django_db
class TestChangePasswordSerializer:
    def test_valid_data(self):
        """有效数据应通过验证"""
        from users.auth_serializers import ChangePasswordSerializer
        data = {'old_password': 'OldPass123', 'new_password': 'NewPass456'}
        serializer = ChangePasswordSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_missing_old_password(self):
        """缺少旧密码应验证失败"""
        from users.auth_serializers import ChangePasswordSerializer
        data = {'new_password': 'NewPass456'}
        serializer = ChangePasswordSerializer(data=data)
        assert not serializer.is_valid()
        assert 'old_password' in serializer.errors

    def test_missing_new_password(self):
        """缺少新密码应验证失败"""
        from users.auth_serializers import ChangePasswordSerializer
        data = {'old_password': 'OldPass123'}
        serializer = ChangePasswordSerializer(data=data)
        assert not serializer.is_valid()
        assert 'new_password' in serializer.errors


# ==================== GuestLoginSerializer 测试 ====================

@pytest.mark.django_db
class TestGuestLoginSerializer:
    def test_creates_guest_user(self):
        """guest 登录应创建新用户"""
        from users.auth_serializers import GuestLoginSerializer
        serializer = GuestLoginSerializer()
        user = serializer.create({})
        assert user.username.startswith('guest_')
        assert user.is_active is True
        assert user.groups.filter(name='Guest').exists()

    def test_each_guest_has_unique_username(self):
        """每次 guest 登录应创建不同用户名的用户"""
        from users.auth_serializers import GuestLoginSerializer
        serializer = GuestLoginSerializer()
        user1 = serializer.create({})
        user2 = serializer.create({})
        assert user1.username != user2.username

    def test_guest_group_created(self):
        """guest 登录应确保 Guest 组存在"""
        from users.auth_serializers import GuestLoginSerializer, ensure_guest_group
        # 确保初始没有 Guest 组
        Group.objects.filter(name='Guest').delete()
        group = ensure_guest_group()
        assert group.name == 'Guest'

    def test_guest_group_reused(self):
        """多次 guest 登录应复用同一个 Guest 组"""
        from users.auth_serializers import GuestLoginSerializer
        serializer = GuestLoginSerializer()
        serializer.create({})
        serializer.create({})
        assert Group.objects.filter(name='Guest').count() == 1


# ==================== UserPersonnelSerializer 测试 ====================

@pytest.mark.django_db
class TestUserPersonnelSerializer:
    def test_link_personnel_to_user(self):
        """UserPersonnelSerializer 应能关联 personnel"""
        from personnel.models import Personnel
        from users.serializers import UserPersonnelSerializer

        user = CustomUser.objects.create_user(username='linked_user', password='pass123')
        personnel = Personnel.objects.create(name='测试员工')

        serializer = UserPersonnelSerializer(instance=user, data={'personnel_id': personnel.id}, partial=True)
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        user.refresh_from_db()
        assert user.personnel == personnel


# ==================== UserAdminSerializer 测试 ====================

@pytest.mark.django_db
class TestUserAdminSerializer:
    def test_admin_serializer_fields(self):
        """UserAdminSerializer 应包含管理字段"""
        from users.serializers import UserAdminSerializer
        user = CustomUser.objects.create_user(username='admin_test', email='at@test.com', password='pass123')
        serializer = UserAdminSerializer(instance=user)
        data = serializer.data
        assert 'username' in data
        assert 'email' in data
        assert 'is_active' in data or 'is_staff' in data

    def test_admin_serializer_create_basic(self):
        """UserAdminSerializer 创建用户时应正确设置基本字段"""
        from users.serializers import UserAdminSerializer
        data = {
            'username': 'created_by_admin',
        }
        serializer = UserAdminSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()
        assert user.username == 'created_by_admin'


# ==================== ensure_guest_group 测试 ====================

@pytest.mark.django_db
class TestEnsureGuestGroup:
    def test_creates_group_if_not_exists(self):
        """Guest 组不存在时应创建"""
        from users.auth_serializers import ensure_guest_group
        Group.objects.filter(name='Guest').delete()
        group = ensure_guest_group()
        assert group.name == 'Guest'

    def test_returns_existing_group(self):
        """Guest 组已存在时应返回现有组"""
        from users.auth_serializers import ensure_guest_group
        existing = Group.objects.create(name='Guest')
        group = ensure_guest_group()
        assert group.id == existing.id
