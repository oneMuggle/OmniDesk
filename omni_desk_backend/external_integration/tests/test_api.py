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
    # 使用公开 IP/域名,避免触发 ``IntegrationService.save()`` 中新增的 SSRF 校验
    return IntegrationService.objects.create(
        name='Test Dify',
        slug='test-dify',
        integration_type='api',
        endpoint_url='http://example.com/api/v1',
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
class TestIntegrationServiceApiKeyContract:
    """API 层契约 (R3-B1):读响应不暴露明文 api_key;PUT 不带 api_key 保留原密钥。"""

    def test_get_response_does_not_expose_api_key(self, authenticated_client, integration_service):
        integration_service.api_key = "super-secret-key"
        integration_service.save(update_fields=["api_key"])

        resp = authenticated_client.get(f"/api/external/integrations/{integration_service.slug}/")

        assert resp.status_code == 200
        assert "api_key" not in resp.data

    def test_update_without_api_key_keeps_existing(self, admin_client):
        """编辑流程契约:PUT 不带 api_key 时保留原密钥(前端「留空不修改」)。"""
        svc = IntegrationService.objects.create(
            name="Keep Key",
            slug="keep-key",
            integration_type="api",
            endpoint_url="http://example.com/api",
            api_key="original-secret",
        )

        resp = admin_client.put(
            f"/api/external/integrations/{svc.slug}/",
            {
                "name": "Keep Key Renamed",
                "slug": "keep-key",
                "integration_type": "api",
                "endpoint_url": "http://example.com/api",
            },
            format="json",
        )

        assert resp.status_code == 200, resp.data
        svc.refresh_from_db()
        assert svc.api_key == "original-secret"
        assert svc.name == "Keep Key Renamed"


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
            'http://100.64.0.1/api',  # CGNAT 段 (100.64.0.0/10)
            'http://100.127.255.254/api',
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

    def test_save_rejects_ssrf_via_orm_bypass(self, db):
        """SECURITY: 直接走 ORM ``save()``(模拟 Django Admin 路径)也必须被 SSRF 校验拦截。

        Django Admin 通过 ``ModelAdmin.save_model`` 直接调用 ``instance.save()``,
        不会经过 DRF serializer 的字段校验;若模型层无独立校验,Admin 路径可注入
        任意 endpoint_url 绕过 API 端的 SSRF 防护。
        """
        from django.core.exceptions import ValidationError

        bad = IntegrationService(
            name='Admin Bypass Attempt',
            slug='admin-bypass-attempt',
            integration_type='api',
            endpoint_url='http://127.0.0.1:8000/admin/',
        )
        with pytest.raises(ValidationError):
            bad.save()

        # 正常 URL 仍可保存
        ok = IntegrationService(
            name='Admin Save OK',
            slug='admin-save-ok',
            integration_type='api',
            endpoint_url='http://example.com/api',
        )
        ok.save()
        assert ok.pk is not None

    def test_save_rejects_cgnat_via_orm(self, db):
        """SECURITY: ``IntegrationService.save()`` 也需拦截 CGNAT 段(100.64.0.0/10)。"""
        from django.core.exceptions import ValidationError

        cgnat = IntegrationService(
            name='CGNAT Attempt',
            slug='cgnat-attempt',
            integration_type='api',
            endpoint_url='http://100.64.0.1/api',
        )
        with pytest.raises(ValidationError):
            cgnat.save()


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
            '0.0.0.0',  # nosec B104 -- 测试 is_forbidden_host 拒绝该 IP,并非真实 socket bind
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

    @pytest.mark.parametrize(
        'host',
        [
            '100.64.0.1',
            '100.64.5.5',
            '100.100.100.100',
            '100.127.255.254',
        ],
    )
    def test_cgnat_blocked(self, host):
        """CGNAT 段(100.64.0.0/10)需被拒绝——Python ``IPv4Address.is_private`` 不覆盖该段。"""
        assert is_forbidden_host(host) is True


@pytest.mark.django_db
class TestProxyServiceReValidation:
    """``ProxyService.forward_post`` 请求前再次校验 endpoint_url,防御 DNS rebinding。"""

    def test_forward_post_rejects_dns_rebinding_to_internal(self, monkeypatch):
        """集成场景: 同一域名创建时解析为合法公网 IP,请求时解析为 127.0.0.1 → 拒绝。"""
        from external_integration.services.plugin_service import ProxyService

        # mock socket.getaddrinfo 让 forward_post 内部 is_forbidden_host 解析到内网 IP
        monkeypatch.setattr(
            socket,
            'getaddrinfo',
            lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 0))],
        )

        result = ProxyService.forward_post(
            endpoint_url='http://attacker.example.com/api',
            payload={'x': 1},
        )
        assert result['status_code'] == 400
        assert '禁止' in result['error']

    def test_forward_post_rejects_cgnat_rebinding(self, monkeypatch):
        """CGNAT rebinding 也应被前向转发层拒绝。"""
        from external_integration.services.plugin_service import ProxyService

        monkeypatch.setattr(
            socket,
            'getaddrinfo',
            lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('100.64.0.1', 0))],
        )

        result = ProxyService.forward_post(
            endpoint_url='http://attacker.example.com/api',
            payload={},
        )
        assert result['status_code'] == 400

    def test_forward_post_allows_when_resolves_to_public(self, monkeypatch):
        """正向路径: 解析到公网 IP 时仍可转发(避免引入回归)。"""
        from unittest.mock import patch

        from external_integration.services.plugin_service import ProxyService

        monkeypatch.setattr(
            socket,
            'getaddrinfo',
            lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 0))],
        )

        class _FakeResp:
            status_code = 200

            def json(self):
                return {'ok': True}

        with patch.object(requests := __import__('requests'), 'post', return_value=_FakeResp()) as mock_post:
            result = ProxyService.forward_post(
                endpoint_url='http://public.example.com/api',
                payload={'x': 1},
            )
        assert result['status_code'] == 200
        assert result['data'] == {'ok': True}
        mock_post.assert_called_once()
