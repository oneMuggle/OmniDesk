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
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200) # 导入 status
        self.assertGreater(len(response.data), 0)
        # 检查是否包含 personnel 字段
        self.assertIn('personnel', response.data[0])

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
