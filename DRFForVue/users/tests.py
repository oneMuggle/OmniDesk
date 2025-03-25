from django.test import TestCase
from rest_framework.test import APIClient
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
