from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from django.urls import reverse
from rest_framework import status # 导入 status
from .models import CustomUser, PhoneNumber
from personnel.models import Personnel  # 导入 Personnel 模型
from django.contrib.auth.models import Group

class UserRegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('users_auth:auth-registration')
        
    def test_valid_registration(self):
        data = {
            'username': 'testuser', # 修改为直接的字符串
            'password': 'Testpass123',
            'password_confirmation': 'Testpass123'
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue('user' in response.data)
        self.assertEqual(CustomUser.objects.count(), 1)

    def test_invalid_username_format(self):
        data = {
            'username': 'test@user', # 修改为直接的字符串
            'password': 'Testpass123',
            'password_confirmation': 'Testpass123'
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.json())

    def test_missing_password(self):
        data = {
            'username': 'testuser', # 修改为直接的字符串
            'password': '',
            'password_confirmation': 'Testpass123'
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.json())

    def test_password_mismatch(self):
        data = {
            'username': 'testuser', # 修改为直接的字符串
            'password': 'Testpass123',
            'password_confirmation': 'Differentpass123'
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.json())

# Create your tests here.

class UserAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='Testpass123',
            email='test@example.com'
        )
        self.login_url = reverse('users_auth:token_obtain_pair')
        self.profile_url = reverse('users:current-user')

    def test_successful_login(self):
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'Testpass123'
        }, format='json')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_invalid_credentials(self):
        response = self.client.post(self.login_url, {
            'username': 'wronguser',
            'password': 'Wrongpass123'
        }, format='json')
        
        self.assertEqual(response.status_code, 401)
        self.assertIn('detail', response.data)

    def test_protected_endpoint_access(self):
        # 未认证用户访问
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED) # Or 401, depending on default auth class

        # 认证用户访问
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'testuser')

    def test_user_profile_retrieval(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['email'], 'test@example.com')

class UserPersonnelManagementTests(APITestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        user_group, _ = Group.objects.get_or_create(name='User')

        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            password='password123',
            is_staff=True
        )
        self.admin_user.groups.add(admin_group)

        self.manager_user = CustomUser.objects.create_user(
            username='manager',
            password='password123',
            is_staff=True
        )
        self.manager_user.groups.add(manager_group)

        self.regular_user = CustomUser.objects.create_user(
            username='user',
            password='password123'
        )
        self.regular_user.groups.add(user_group)
        self.personnel1 = Personnel.objects.create(name='张三', id_card_number='111111111111111111')
        self.personnel2 = Personnel.objects.create(name='李四', id_card_number='222222222222222222')

        self.client = APIClient()
        self.list_url = reverse('users:user-admin-list') # 'users' 命名空间已在 omni_desk_backend/urls.py 中定义

    def test_admin_can_list_users_with_personnel(self):
        self.client.force_authenticate(user=self.admin_user)
        CustomUser.objects.create_user(username='test_list_user', password='password123')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
        # 检查是否包含 personnel 字段
        self.assertIn('personnel', response.data['results'][0])

    def test_admin_can_associate_personnel_to_user(self):
        self.client.force_authenticate(user=self.admin_user)
        user_to_update = CustomUser.objects.create_user(username='test_associate', password='password123')
        update_url = reverse('users:user-personnel-detail', args=[user_to_update.id]) # 确保这里是正确的 URL name
        
        data = {'personnel_id': self.personnel1.id}
        response = self.client.patch(update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_to_update.refresh_from_db()
        self.assertEqual(user_to_update.personnel, self.personnel1)

    def test_admin_can_disassociate_personnel_from_user(self):
        self.client.force_authenticate(user=self.admin_user)
        user_to_update = CustomUser.objects.create_user(username='test_disassociate', password='password123', personnel=self.personnel1)
        update_url = reverse('users:user-personnel-detail', args=[user_to_update.id])

        data = {'personnel_id': ''} # 空字符串表示解除关联
        response = self.client.patch(update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_to_update.refresh_from_db()
        self.assertIsNone(user_to_update.personnel)

    def test_manager_can_associate_personnel_to_user(self):
        self.client.force_authenticate(user=self.manager_user)
        user_to_update = CustomUser.objects.create_user(username='test_manager_associate', password='password123')
        update_url = reverse('users:user-personnel-detail', args=[user_to_update.id])
        
        data = {'personnel_id': self.personnel2.id}
        response = self.client.patch(update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_to_update.refresh_from_db()
        self.assertEqual(user_to_update.personnel, self.personnel2)

    def test_regular_user_cannot_associate_personnel(self):
        self.client.force_authenticate(user=self.regular_user)
        user_to_update = CustomUser.objects.create_user(username='test_regular_user', password='password123')
        update_url = reverse('users:user-personnel-detail', args=[user_to_update.id])
        
        data = {'personnel_id': self.personnel1.id}
        response = self.client.patch(update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN) # 应该没有权限

class UserProfileManagementTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='password123',
            real_name='Old Name'
        )
        PhoneNumber.objects.create(user=self.user, number='1234567890')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.profile_update_url = reverse('users:user-profile-update')
        self.change_password_url = reverse('users:change-password')

    def test_user_can_update_profile(self):
        data = {
            'real_name': 'New Name',
            'phone_numbers': [{'number': '0987654321'}]
        }
        response = self.client.patch(self.profile_update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.real_name, 'New Name')
        self.assertEqual(self.user.phone_numbers.first().number, '0987654321')

    def test_user_can_change_password(self):
        data = {
            'old_password': 'password123',
            'new_password': 'newpassword456'
        }
        response = self.client.put(self.change_password_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpassword456'))

    def test_change_password_with_wrong_old_password(self):
        data = {
            'old_password': 'wrongpassword',
            'new_password': 'newpassword456'
        }
        response = self.client.put(self.change_password_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class UserAdminViewTests(APITestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        user_group, _ = Group.objects.get_or_create(name='User')

        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            password='password123',
            is_staff=True,
            is_superuser=True
        )
        self.admin_user.groups.add(admin_group)

        self.manager_user = CustomUser.objects.create_user('manager', 'manager@test.com', 'password123')
        self.manager_user.groups.add(manager_group)

        self.regular_user = CustomUser.objects.create_user('user', 'user@test.com', 'password123')
        self.regular_user.groups.add(user_group)
        self.client = APIClient()
        self.user_admin_list_url = reverse('users:user-admin-list')
        self.user_admin_detail_url = reverse('users:user-admin-detail', args=[self.regular_user.id])

    def test_admin_can_access_user_admin_list(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.user_admin_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_manager_cannot_access_user_admin_list(self):
        self.client.force_authenticate(user=self.manager_user)
        response = self.client.get(self.user_admin_list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_cannot_access_user_admin_list(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.user_admin_list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_access_user_admin_detail(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.user_admin_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_update_user_group(self):
        self.client.force_authenticate(user=self.admin_user)
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        data = {'groups': [manager_group.id]}
        response = self.client.patch(self.user_admin_detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertIn(manager_group, self.regular_user.groups.all())


class UserModelTests(TestCase):
    def test_user_str(self):
        """Test the string representation of the CustomUser model."""
        user = CustomUser.objects.create_user(username='testuser_str', password='password')
        self.assertEqual(str(user), 'testuser_str')


class PhoneNumberModelTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser_phone', password='password')

    def test_phone_number_str(self):
        """Test the string representation of the PhoneNumber model."""
        phone = PhoneNumber.objects.create(user=self.user, number='1234567890')
        self.assertEqual(str(phone), '1234567890')

    def test_phone_number_creation(self):
        """Test creating a phone number and associating it with a user."""
        PhoneNumber.objects.create(user=self.user, number='1112223333')
        self.assertEqual(self.user.phone_numbers.count(), 1)
        self.assertEqual(self.user.phone_numbers.first().number, '1112223333')

from .serializers import UserRegistrationSerializer, UserLoginSerializer, CustomTokenObtainPairSerializer, UserDetailSerializer
from rest_framework import serializers
from django.core.cache import cache

class UserSerializerTests(TestCase):
    def setUp(self):
        # 清除权限缓存，防止前面测试的缓存污染
        cache.clear()

    def test_registration_serializer_validate_username_whitespace(self):
        """Test that username validation strips whitespace."""
        serializer = UserRegistrationSerializer()
        validated_username = serializer.validate_username("  testuser  ")
        self.assertEqual(validated_username, "testuser")

    def test_login_serializer_inactive_user(self):
        """Test that an inactive user cannot log in."""
        user = CustomUser.objects.create_user(username='inactive', password='password')
        user.is_active = False
        user.save()
        data = {'username': 'inactive', 'password': 'password'}
        serializer = UserLoginSerializer(data=data)
        with self.assertRaises(serializers.ValidationError) as cm:
            serializer.is_valid(raise_exception=True)
        self.assertIn("用户账户已被禁用", str(cm.exception.detail['non_field_errors'][0]))

    def test_custom_token_serializer_admin_permissions(self):
        """Test that admin users get correct permissions in their token."""
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        admin_user = CustomUser.objects.create_user(username='token_admin', password='password')
        admin_user.groups.add(admin_group)
        serializer = CustomTokenObtainPairSerializer(data={'username': 'token_admin', 'password': 'password'})
        self.assertTrue(serializer.is_valid())
        data = serializer.validated_data
        self.assertIn('permissions', data)
        self.assertIn('events.manage_schedule', data['permissions'])
        self.assertIn('documents.view_book', data['permissions'])

    def test_custom_token_serializer_manager_permissions(self):
        """Test that manager users get correct permissions in their token."""
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        manager_user = CustomUser.objects.create_user(username='token_manager', password='password')
        manager_user.groups.add(manager_group)
        serializer = CustomTokenObtainPairSerializer(data={'username': 'token_manager', 'password': 'password'})
        self.assertTrue(serializer.is_valid())
        data = serializer.validated_data
        self.assertIn('permissions', data)
        self.assertIn('events.manage_personnel', data['permissions'])
        self.assertNotIn('some.admin.permission', data['permissions'])

    def test_user_detail_serializer_update_phone_numbers(self):
        """Test updating a user's phone numbers via the UserDetailSerializer."""
        user = CustomUser.objects.create_user(username='phone_updater', password='password')
        PhoneNumber.objects.create(user=user, number='111')
        
        data = {
            'phone_numbers': [
                {'number': '222'},
                {'number': '333'}
            ]
        }
        serializer = UserDetailSerializer(instance=user, data=data, partial=True)
        self.assertTrue(serializer.is_valid(raise_exception=True))
        serializer.save()
        user.refresh_from_db()
        self.assertEqual(user.phone_numbers.count(), 2)
        numbers = list(user.phone_numbers.values_list('number', flat=True))
        self.assertIn('222', numbers)
        self.assertIn('333', numbers)
        self.assertNotIn('111', numbers)

class UserViewTests(APITestCase):
    def setUp(self):
        CustomUser.objects.all().delete()
        admin_group, _ = Group.objects.get_or_create(name='Admin')
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        self.admin_user = CustomUser.objects.create_user(username='view_admin', password='password', is_staff=True)
        self.admin_user.groups.add(admin_group)
        self.manager_user = CustomUser.objects.create_user(username='view_manager', password='password')
        self.manager_user.groups.add(manager_group)
        self.user1 = CustomUser.objects.create_user(username='view_user1', password='password', real_name='张三')
        self.user2 = CustomUser.objects.create_user(username='view_user2', password='password', real_name='李四')
        
        self.personnel_list_url = reverse('users:user-personnel-list')

    def test_personnel_list_search(self):
        """Test searching personnel list by real_name."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.personnel_list_url, {'search': '张三'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['real_name'], '张三')

    def test_user_personnel_viewset_update(self):
        """Test updating personnel association via UserPersonnelViewSet."""
        self.client.force_authenticate(user=self.admin_user)
        personnel = Personnel.objects.create(name='王五', id_card_number='333333333333333333')
        update_url = reverse('users:user-personnel-detail', args=[self.user1.id])
        
        # Associate
        response = self.client.patch(update_url, {'personnel_id': personnel.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user1.refresh_from_db()
        self.assertEqual(self.user1.personnel, personnel)
        self.assertEqual(self.user1.real_name, '王五')

        # Disassociate
        response = self.client.patch(update_url, {'personnel_id': ''}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user1.refresh_from_db()
        self.assertIsNone(self.user1.personnel)
