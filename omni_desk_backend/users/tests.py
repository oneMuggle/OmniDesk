from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from django.urls import reverse
from rest_framework import status # 导入 status
from .models import CustomUser
from events.models import Personnel # 导入 Personnel 模型

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
        self.assertIn('username', response.data['validation_errors'])

    def test_missing_password(self):
        data = {
            'username': 'testuser', # 修改为直接的字符串
            'password': '',
            'password_confirmation': 'Testpass123'
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.data['validation_errors'])

    def test_password_mismatch(self):
        data = {
            'username': 'testuser', # 修改为直接的字符串
            'password': 'Testpass123',
            'password_confirmation': 'Differentpass123'
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.data['validation_errors'])

# Create your tests here.

class UserAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='Testpass123',
            email='test@example.com'
        )
        self.login_url = reverse('users_auth:auth-login')
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
        self.assertEqual(response.status_code, 401)

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
        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            password='password123',
            role='admin'
        )
        self.manager_user = CustomUser.objects.create_user(
            username='manager',
            password='password123',
            role='manager'
        )
        self.regular_user = CustomUser.objects.create_user(
            username='user',
            password='password123',
            role='user'
        )
        self.personnel1 = Personnel.objects.create(name='张三')
        self.personnel2 = Personnel.objects.create(name='李四')

        self.client = APIClient()
        self.list_url = reverse('users:customuser-list') # 'users' 命名空间已在 omni_desk_backend/urls.py 中定义

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
        update_url = reverse('users:customuser-detail', args=[user_to_update.id]) # 确保这里是正确的 URL name
        
        data = {'personnel_id': self.personnel1.id}
        response = self.client.patch(update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_to_update.refresh_from_db()
        self.assertEqual(user_to_update.personnel, self.personnel1)

    def test_admin_can_disassociate_personnel_from_user(self):
        self.client.force_authenticate(user=self.admin_user)
        user_to_update = CustomUser.objects.create_user(username='test_disassociate', password='password123', personnel=self.personnel1)
        update_url = reverse('users:customuser-detail', args=[user_to_update.id])

        data = {'personnel_id': ''} # 空字符串表示解除关联
        response = self.client.patch(update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_to_update.refresh_from_db()
        self.assertIsNone(user_to_update.personnel)

    def test_manager_can_associate_personnel_to_user(self):
        self.client.force_authenticate(user=self.manager_user)
        user_to_update = CustomUser.objects.create_user(username='test_manager_associate', password='password123')
        update_url = reverse('users:customuser-detail', args=[user_to_update.id])
        
        data = {'personnel_id': self.personnel2.id}
        response = self.client.patch(update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_to_update.refresh_from_db()
        self.assertEqual(user_to_update.personnel, self.personnel2)

    def test_regular_user_cannot_associate_personnel(self):
        self.client.force_authenticate(user=self.regular_user)
        user_to_update = CustomUser.objects.create_user(username='test_regular_user', password='password123')
        update_url = reverse('users:customuser-detail', args=[user_to_update.id])
        
        data = {'personnel_id': self.personnel1.id}
        response = self.client.patch(update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN) # 应该没有权限

class UserProfileManagementTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='password123',
            real_name='Old Name',
            phone='1234567890'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.profile_update_url = reverse('users:user-profile-update')
        self.change_password_url = reverse('users:change-password')

    def test_user_can_update_profile(self):
        data = {
            'real_name': 'New Name',
            'phone': '0987654321'
        }
        response = self.client.patch(self.profile_update_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.real_name, 'New Name')
        self.assertEqual(self.user.phone, '0987654321')

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
        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            password='password123',
            role='admin',
            is_staff=True,
            is_superuser=True
        )
        self.manager_user = CustomUser.objects.create_user('manager', 'manager@test.com', 'password123', role='manager')
        self.regular_user = CustomUser.objects.create_user('user', 'user@test.com', 'password123', role='user')
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

    def test_admin_can_update_user_role(self):
        self.client.force_authenticate(user=self.admin_user)
        data = {'role': 'manager'}
        response = self.client.patch(self.user_admin_detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.role, 'manager')
