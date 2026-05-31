"""
Authentication flow tests: registration, login, token refresh, guest login.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from users.models import CustomUser


@pytest.mark.django_db
class TestUserRegistration:
    def test_registration_success(self, api_client):
        data = {
            'username': 'newuser123',
            'password': 'SecurePass123!',
            'password_confirmation': 'SecurePass123!',
            'real_name': 'Test User',
        }
        response = api_client.post(reverse('users_auth:auth-registration'), data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
        assert CustomUser.objects.filter(username='newuser123').exists()

    def test_registration_duplicate_username(self, api_client):
        data = {
            'username': 'newuser123',
            'password': 'SecurePass123!',
            'password_confirmation': 'SecurePass123!',
        }
        api_client.post(reverse('users_auth:auth-registration'), data, format='json')
        response = api_client.post(reverse('users_auth:auth-registration'), data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False


@pytest.mark.django_db
class TestUserLogin:
    def test_login_success(self, api_client, regular_user_obj):
        data = {'username': 'regular_test', 'password': 'user123'}
        response = api_client.post(reverse('users_auth:token_obtain_pair'), data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_login_wrong_password(self, api_client, regular_user_obj):
        data = {'username': 'regular_test', 'password': 'wrong_password'}
        response = api_client.post(reverse('users_auth:token_obtain_pair'), data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user(self, api_client):
        data = {'username': 'nonexistent', 'password': 'somepass'}
        response = api_client.post(reverse('users_auth:token_obtain_pair'), data, format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestTokenRefresh:
    def test_token_refresh_success(self, api_client, regular_user_obj):
        login_data = {'username': 'regular_test', 'password': 'user123'}
        login_resp = api_client.post(reverse('users_auth:token_obtain_pair'), login_data, format='json')
        assert login_resp.status_code == status.HTTP_200_OK

        refresh_data = {'refresh': login_resp.data['refresh']}
        response = api_client.post(reverse('users_auth:token-refresh'), refresh_data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data


@pytest.mark.django_db
class TestGuestLogin:
    def test_guest_login_success(self, api_client):
        response = api_client.post(reverse('users_auth:guest-login'), {}, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert response.data.get('is_guest') is True


@pytest.mark.django_db
class TestCurrentUser:
    def test_get_current_user(self, regular_client, regular_user_obj):
        response = regular_client.get(reverse('users:current-user'))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == 'regular_test'

    def test_current_user_unauthenticated(self, api_client):
        response = api_client.get(reverse('users:current-user'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestChangePassword:
    def test_change_password_success(self, regular_client, regular_user_obj):
        data = {
            'old_password': 'user123',
            'new_password': 'NewSecurePass456!',
        }
        response = regular_client.put(reverse('users:change-password'), data, format='json')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        regular_user_obj.refresh_from_db()
        assert regular_user_obj.check_password('NewSecurePass456!')

    def test_change_password_wrong_old(self, regular_client, regular_user_obj):
        data = {
            'old_password': 'wrong_old',
            'new_password': 'NewSecurePass456!',
        }
        response = regular_client.put(reverse('users:change-password'), data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
