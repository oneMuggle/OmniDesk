from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from django.urls import reverse
from .models import CustomUser

class UserRegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('user-register')
        
    def test_valid_registration(self):
        data = {
            'username': {'username': 'testuser'},
            'password': 'Testpass123',
            'password_confirmation': 'Testpass123'
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue('user' in response.data)
        self.assertEqual(CustomUser.objects.count(), 1)

    def test_invalid_username_format(self):
        data = {
            'username': {'username': 'test@user'},
            'password': 'Testpass123',
            'password_confirmation': 'Testpass123'
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.data['validation_errors'])

    def test_missing_password(self):
        data = {
            'username': {'username': 'testuser'},
            'password': '',
            'password_confirmation': 'Testpass123'
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.data['validation_errors'])

    def test_password_mismatch(self):
        data = {
            'username': {'username': 'testuser'},
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
        self.login_url = reverse('token-obtain-pair')
        self.profile_url = reverse('user-profile')

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
