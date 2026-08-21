"""
Authentication flow tests: registration, login, token refresh, guest login.
"""
import uuid

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

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
        # 修复后:返回 DRF 标准格式 {field: [errors]},不再有 success: False wrapper
        assert 'username' in response.json()


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

    def test_guest_login_sets_expiry(self, api_client):
        """游客登录后 guest_until 应为 now()+24h 左右。"""
        from datetime import timedelta
        from django.utils import timezone

        response = api_client.post(reverse('users_auth:guest-login'), {}, format='json')
        assert response.status_code == status.HTTP_200_OK

        user = CustomUser.objects.filter(username__startswith='guest_').latest('date_joined')
        assert user.guest_until is not None
        expected = timezone.now() + timedelta(hours=24)
        assert abs((user.guest_until - expected).total_seconds()) < 60


@pytest.mark.django_db
class TestGuestExpiry:
    """R5-A2: 游客账号过期拦截与清理。"""

    def _make_guest(self, hours_delta):
        from datetime import timedelta
        from django.utils import timezone

        user = CustomUser.objects.create_user(
            username=f'guest_{uuid.uuid4().hex[:12]}',
            password=uuid.uuid4().hex,
        )
        user.guest_until = timezone.now() + timedelta(hours=hours_delta)
        user.save()
        return user

    def test_expired_guest_blocked_on_me(self, api_client):
        """已过期游客访问 /users/me/ 应返回 401。"""
        user = self._make_guest(hours_delta=-1)
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse('users:current-user'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_active_guest_allowed_on_me(self, api_client):
        """未过期游客可正常访问 /users/me/。"""
        user = self._make_guest(hours_delta=24)
        api_client.force_authenticate(user=user)
        response = api_client.get(reverse('users:current-user'))
        assert response.status_code == status.HTTP_200_OK

    def test_regular_user_unaffected(self, regular_user_obj, api_client):
        """普通用户无 guest_until,不受过期拦截影响。"""
        api_client.force_authenticate(user=regular_user_obj)
        response = api_client.get(reverse('users:current-user'))
        assert response.status_code == status.HTTP_200_OK

    def test_cleanup_deletes_only_expired(self):
        """清理任务只删除已过期游客,保留活跃游客和普通用户。"""
        from users.tasks import cleanup_expired_guest_users

        expired = self._make_guest(hours_delta=-1)
        active = self._make_guest(hours_delta=24)
        regular = CustomUser.objects.create_user(username='regular_keep', password='x')

        result = cleanup_expired_guest_users()

        assert not CustomUser.objects.filter(id=expired.id).exists()
        assert CustomUser.objects.filter(id=active.id).exists()
        assert CustomUser.objects.filter(id=regular.id).exists()


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


@pytest.mark.django_db
class TestDjangoAdminLogin:
    """R4-A4: JWT → Session 转换端点的安全改造测试。

    端点仅接受 POST + ``Authorization: Bearer <token>`` header,
    token 不再通过 query string 携带(避免泄露到 nginx 日志/浏览器历史/Referer)。
    同时要求 staff/superuser 权限,并套上 5/15m 限流。
    """

    def _admin_token(self, user):
        return str(RefreshToken.for_user(user).access_token)

    def test_login_success_redirects_to_admin(self, api_client, admin_user_obj):
        url = reverse('users:django-admin-login')
        resp = api_client.post(
            url,
            HTTP_AUTHORIZATION=f"Bearer {self._admin_token(admin_user_obj)}",
        )
        assert resp.status_code == status.HTTP_302_FOUND
        assert resp['Location'] == '/admin/'

    def test_missing_token_returns_400(self, api_client):
        resp = api_client.post(reverse('users:django-admin-login'))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_token_returns_401(self, api_client):
        resp = api_client.post(
            reverse('users:django-admin-login'),
            HTTP_AUTHORIZATION="Bearer invalid.token.value",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_staff_user_returns_403(self, api_client, regular_user_obj):
        resp = api_client.post(
            reverse('users:django-admin-login'),
            HTTP_AUTHORIZATION=f"Bearer {self._admin_token(regular_user_obj)}",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_get_method_returns_405(self, api_client, admin_user_obj):
        resp = api_client.get(reverse('users:django-admin-login'))
        assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @override_settings(RATELIMIT_ENABLE=True)
    def test_rate_limited_after_five_requests(self, api_client, admin_user_obj):
        """同 IP 15 分钟内超过 5 次 POST 触发限流(429)。

        测试 settings 默认 RATELIMIT_ENABLE=False(禁用限流),
        本用例显式开启以验证装饰器生效。
        """
        url = reverse('users:django-admin-login')
        auth = {'HTTP_AUTHORIZATION': f"Bearer {self._admin_token(admin_user_obj)}"}
        for _ in range(5):
            resp = api_client.post(url, **auth)
            assert resp.status_code == status.HTTP_302_FOUND
        # 第 6 次触发限流
        resp = api_client.post(url, **auth)
        assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
