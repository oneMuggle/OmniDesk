"""
Auth flow integration tests — end-to-end API chains.

Tests the complete lifecycle: register → login → get JWT → access protected
endpoints → refresh token → change password → guest login.

Uses real JWT tokens (not force_authenticate) to verify end-to-end behaviour.
"""
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

REGISTRATION_URL = '/api/auth/registration/'
LOGIN_URL = '/api/auth/login/'
TOKEN_REFRESH_URL = '/api/auth/token/refresh/'
GUEST_LOGIN_URL = '/api/auth/guest-login/'
ME_URL = '/api/users/me/'
CHANGE_PASSWORD_URL = '/api/users/me/change-password/'

REGISTRATION_DATA = {
    'username': 'flow_test_user',
    'password': 'FlowTest123',
    'password_confirmation': 'FlowTest123',
}


class FullAuthFlowTests(APITestCase):
    """Chain registration → login → protected access in single tests."""

    def test_register_login_access_protected(self):
        """Register → login → use JWT token to GET /users/me/."""
        # Step 1: Register
        resp = self.client.post(REGISTRATION_URL, REGISTRATION_DATA, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['username'], 'flow_test_user')

        # Step 2: Login
        resp = self.client.post(LOGIN_URL, {
            'username': 'flow_test_user',
            'password': 'FlowTest123',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)
        self.assertIn('permissions', resp.data)

        access = resp.data['access']

        # Step 3: Access protected endpoint with real JWT
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        resp = self.client.get(ME_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['username'], 'flow_test_user')

    def test_token_refresh_flow(self):
        """Login → refresh token → use new access token on protected endpoint."""
        self.client.post(REGISTRATION_URL, REGISTRATION_DATA, format='json')
        resp = self.client.post(LOGIN_URL, {
            'username': 'flow_test_user',
            'password': 'FlowTest123',
        }, format='json')
        refresh_token = resp.data['refresh']

        resp = self.client.post(TOKEN_REFRESH_URL, {
            'refresh': refresh_token,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)

        new_access = resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access}')
        resp = self.client.get(ME_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_invalid_token_rejected(self):
        """Fake JWT token should be rejected with 401."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer faketoken.invalid.signature')
        resp = self.client.get(ME_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_full_lifecycle_with_password_change(self):
        """Register → login → change password → login with new password → old password fails."""
        self.client.post(REGISTRATION_URL, REGISTRATION_DATA, format='json')
        resp = self.client.post(LOGIN_URL, {
            'username': 'flow_test_user',
            'password': 'FlowTest123',
        }, format='json')
        access = resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        # Change password
        resp = self.client.put(CHANGE_PASSWORD_URL, {
            'old_password': 'FlowTest123',
            'new_password': 'NewFlow456',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

        # Old password should fail
        self.client.credentials()
        resp = self.client.post(LOGIN_URL, {
            'username': 'flow_test_user',
            'password': 'FlowTest123',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # New password should succeed
        resp = self.client.post(LOGIN_URL, {
            'username': 'flow_test_user',
            'password': 'NewFlow456',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class GuestLoginFlowTests(APITestCase):
    """Guest login → token → protected access → permission verification."""

    def test_guest_login_returns_tokens(self):
        """POST guest-login → returns access, refresh, is_guest."""
        resp = self.client.post(GUEST_LOGIN_URL, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)
        self.assertTrue(resp.data['is_guest'])

    def test_guest_can_access_protected_endpoint(self):
        """Guest login → use token to GET /users/me/."""
        resp = self.client.post(GUEST_LOGIN_URL, {}, format='json')
        access = resp.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        resp = self.client.get(ME_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['username'].startswith('guest_'))

    def test_guest_token_refresh(self):
        """Guest login → refresh → use new token on protected endpoint."""
        resp = self.client.post(GUEST_LOGIN_URL, {}, format='json')
        refresh_token = resp.data['refresh']

        resp = self.client.post(TOKEN_REFRESH_URL, {
            'refresh': refresh_token,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {resp.data["access"]}')
        resp = self.client.get(ME_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_guest_has_no_permissions(self):
        """Guest login → response permissions should be empty list."""
        resp = self.client.post(GUEST_LOGIN_URL, {}, format='json')
        self.assertEqual(resp.data['permissions'], [])
