import socket

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from ..models import IntegrationService, Plugin
from ..serializers import is_forbidden_host

CustomUser = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='testuser', password='testpass')


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_user(db):
    return CustomUser.objects.create_user(username='adminuser', password='adminpass', is_staff=True)


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def integration_service(db):
    return IntegrationService.objects.create(
        name='Test Dify',
        slug='test-dify',
        integration_type='api',
        endpoint_url='http://dify.internal/api/v1',
    )


@pytest.fixture
def plugin(db):
    return Plugin.objects.create(
        name='Test Plugin',
        slug='test-plugin',
        category='test',
        status='pending_review',
    )


@pytest.mark.django_db
class TestIntegrationServiceAPI:
    def test_list_services_unauthenticated(self, api_client):
        resp = api_client.get('/api/external/integrations/')
        assert resp.status_code == 401

    def test_list_services_empty(self, authenticated_client):
        resp = authenticated_client.get('/api/external/integrations/')
        assert resp.status_code == 200
        assert resp.data['results'] == []

    def test_list_services(self, authenticated_client, integration_service):
        resp = authenticated_client.get('/api/external/integrations/')
        assert resp.status_code == 200
        assert resp.data['count'] == 1
        assert len(resp.data['results']) == 1
        assert resp.data['results'][0]['slug'] == 'test-dify'

    def test_get_service_by_slug(self, authenticated_client, integration_service):
        resp = authenticated_client.get(f'/api/external/integrations/{integration_service.slug}/')
        assert resp.status_code == 200
        assert resp.data['name'] == 'Test Dify'

    def test_embed_not_iframe_type(self, authenticated_client, integration_service):
        resp = authenticated_client.get(f'/api/external/integrations/{integration_service.slug}/embed/')
        assert resp.status_code == 400

    def test_proxy_forbidden_for_regular_user(self, authenticated_client, integration_service):
        """普通用户禁止触发服务端代理调用（SSRF 防护）。"""
        resp = authenticated_client.post(f'/api/external/integrations/{integration_service.slug}/proxy/', {})
        assert resp.status_code == 403

    def test_proxy_not_api_type_as_admin(self, admin_client):
        svc = IntegrationService.objects.create(
            name='Test Iframe',
            slug='test-iframe',
            integration_type='iframe',
            endpoint_url='http://example.com',
        )
        resp = admin_client.post(f'/api/external/integrations/{svc.slug}/proxy/', {})
        assert resp.status_code == 400


@pytest.mark.django_db
class TestIntegrationServiceSecurity:
    """SSRF 防护与写操作权限收紧测试。"""

    def _payload(self, endpoint_url):
        return {
            'name': 'Sec Service',
            'slug': 'sec-service',
            'integration_type': 'api',
            'endpoint_url': endpoint_url,
        }

    def test_create_forbidden_for_regular_user(self, authenticated_client):
        resp = authenticated_client.post(
            '/api/external/integrations/', self._payload('http://93.184.216.34/api'), format='json'
        )
        assert resp.status_code == 403

    @pytest.mark.parametrize(
        'endpoint_url',
        [
            'http://127.0.0.1:8000/api',
            'http://10.0.0.5/api',
            'http://172.16.3.4/api',
            'http://192.168.1.100/api',
            'http://169.254.169.254/latest/meta-data/',  # 云元数据地址
            'http://0.0.0.0:8000/api',
            'http://localhost:8000/api',
            'http://[::1]:8000/api',
            'http://[fc00::1]/api',
        ],
    )
    def test_create_with_internal_url_rejected(self, admin_client, endpoint_url):
        resp = admin_client.post('/api/external/integrations/', self._payload(endpoint_url), format='json')
        assert resp.status_code == 400
        assert 'endpoint_url' in resp.data

    def test_create_with_non_http_scheme_rejected(self, admin_client):
        resp = admin_client.post('/api/external/integrations/', self._payload('file:///etc/passwd'), format='json')
        assert resp.status_code == 400
        assert 'endpoint_url' in resp.data

    def test_create_with_public_url_allowed(self, admin_client):
        resp = admin_client.post(
            '/api/external/integrations/', self._payload('http://93.184.216.34/api'), format='json'
        )
        assert resp.status_code == 201


@pytest.mark.django_db
class TestPluginPermissions:
    """插件写操作 / 审核 / 执行权限测试。"""

    def test_list_plugins_allowed_for_regular_user(self, authenticated_client, plugin):
        resp = authenticated_client.get('/api/external/plugins/')
        assert resp.status_code == 200

    def test_create_plugin_forbidden_for_regular_user(self, authenticated_client):
        resp = authenticated_client.post(
            '/api/external/plugins/', {'name': 'P2', 'slug': 'p2', 'category': 'c'}, format='json'
        )
        assert resp.status_code == 403

    def test_review_forbidden_for_regular_user(self, authenticated_client, plugin):
        resp = authenticated_client.post(f'/api/external/plugins/{plugin.id}/review/', {'action': 'approve'})
        assert resp.status_code == 403
        plugin.refresh_from_db()
        assert plugin.status == 'pending_review'

    def test_review_allowed_for_admin(self, admin_client, plugin):
        resp = admin_client.post(f'/api/external/plugins/{plugin.id}/review/', {'action': 'approve'})
        assert resp.status_code == 200
        plugin.refresh_from_db()
        assert plugin.status == 'approved'

    def test_upload_version_forbidden_for_regular_user(self, authenticated_client, plugin):
        uploaded = SimpleUploadedFile('plugin.zip', b'dummy', content_type='application/zip')
        resp = authenticated_client.post(
            f'/api/external/plugins/{plugin.id}/upload_version/', {'file': uploaded}, format='multipart'
        )
        assert resp.status_code == 403

    def test_execute_unapproved_plugin_rejected(self, authenticated_client, plugin):
        """未通过审核的插件禁止执行（execute 本身对普通用户开放，但前置校验拦截）。"""
        resp = authenticated_client.post(f'/api/external/plugins/{plugin.id}/execute/', {}, format='json')
        assert resp.status_code == 403

    def test_execute_approved_plugin_without_active_version(self, authenticated_client, plugin):
        plugin.status = 'approved'
        plugin.save(update_fields=['status'])
        resp = authenticated_client.post(f'/api/external/plugins/{plugin.id}/execute/', {}, format='json')
        assert resp.status_code == 400


class TestIsForbiddenHost:
    """SSRF 工具函数 is_forbidden_host 单元测试。"""

    @pytest.mark.parametrize(
        'host',
        [
            '127.0.0.1',
            '10.0.0.5',
            '172.16.0.1',
            '172.31.255.255',
            '192.168.1.1',
            '169.254.169.254',
            '0.0.0.0',
            'localhost',
            'LOCALHOST',
            '::1',
            '[::1]',
            'fc00::1',
            '',
        ],
    )
    def test_forbidden_hosts(self, host):
        assert is_forbidden_host(host) is True

    @pytest.mark.parametrize('host', ['93.184.216.34', '8.8.8.8', '172.32.0.1', '11.0.0.1'])
    def test_allowed_literal_ips(self, host):
        assert is_forbidden_host(host) is False

    def test_hostname_resolving_to_internal_rejected(self, monkeypatch):
        monkeypatch.setattr(
            socket, 'getaddrinfo', lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 0))]
        )
        assert is_forbidden_host('internal.example.com') is True

    def test_hostname_resolving_to_public_allowed(self, monkeypatch):
        monkeypatch.setattr(
            socket,
            'getaddrinfo',
            lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 0))],
        )
        assert is_forbidden_host('public.example.com') is False

    def test_unresolvable_hostname_rejected(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise socket.gaierror('Name or service not known')

        monkeypatch.setattr(socket, 'getaddrinfo', _raise)
        assert is_forbidden_host('nonexistent.invalid') is True
