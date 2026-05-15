import logging

import requests

logger = logging.getLogger(__name__)


class SsoService:
    """SSO token generation and redirect URL construction."""

    @staticmethod
    def generate_redirect_url(link) -> dict:
        """Generate SSO redirect URL for a given external link."""
        token = f'sso_placeholder_{link.id}'
        redirect_url = f'{link.url}?token={token}'
        return {'redirect_url': redirect_url}


class ProxyService:
    """API proxy for forwarding requests to external services."""

    @staticmethod
    def forward_post(endpoint_url: str, payload: dict, api_key: str | None = None, timeout: int = 30) -> dict:
        """Forward a POST request to an external service and return the response."""
        headers = {}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        try:
            resp = requests.post(endpoint_url, json=payload, headers=headers, timeout=timeout)
            return {'data': resp.json(), 'status_code': resp.status_code}
        except requests.exceptions.Timeout:
            return {'error': '外部服务响应超时', 'status_code': 504}
        except requests.exceptions.ConnectionError:
            return {'error': '无法连接到外部服务', 'status_code': 502}


class PluginExecutionService:
    """Plugin upload, execution, and review management."""

    @staticmethod
    def process_upload(plugin, uploaded_file, file_hash: str, version: str, request) -> dict:
        """Process a new plugin version upload and extract manifest if available."""
        import zipfile
        import json

        from external_integration.models import PluginVersion
        from external_integration.plugin_loader import validate_manifest

        version_obj = PluginVersion.objects.create(
            plugin=plugin,
            version=version,
            upload_file=uploaded_file,
            file_hash=file_hash,
            uploaded_by=request.user,
        )

        try:
            with zipfile.ZipFile(version_obj.upload_file.path, 'r') as zf:
                if 'manifest.json' in zf.namelist():
                    manifest_data = json.loads(zf.read('manifest.json'))
                    validate_manifest(manifest_data)
                    version_obj.manifest = manifest_data
                    version_obj.save()
        except Exception as e:
            logger.warning('插件 manifest 解析失败: %s', e)

        return {
            'id': version_obj.id,
            'version': version_obj.version,
            'file_hash': file_hash,
        }

    @staticmethod
    def execute_plugin(plugin, request) -> dict:
        """Execute the active version of a plugin and log the result."""
        from external_integration.models import PluginCallLog
        from external_integration.plugin_loader import extract_plugin_zip
        from external_integration.plugin_sandbox import execute_plugin_safely

        active_version = plugin.versions.filter(is_active=True).first()
        if not active_version:
            return {'success': False, 'error': '没有已激活的插件版本', 'status_code': 400}

        try:
            tmp_dir = extract_plugin_zip(active_version.upload_file)
            manifest = active_version.manifest or {'entry_point': 'executable', 'timeout_seconds': 30}
            result = execute_plugin_safely(tmp_dir, manifest, request.data)

            PluginCallLog.objects.create(
                plugin_version=active_version,
                user=request.user,
                method='execute',
                args_summary=str(request.data)[:500],
                status='success' if result['success'] else 'error',
                execution_time_ms=result.get('execution_time_ms'),
                error_message=result.get('error'),
            )

            return {'success': True, 'data': result}
        except Exception as e:
            return {'success': False, 'error': str(e), 'status_code': 500}

    @staticmethod
    def review_plugin(plugin, action_type: str, notes: str = '') -> dict:
        """Approve or reject a plugin."""
        if action_type == 'approve':
            plugin.status = 'approved'
        elif action_type == 'reject':
            plugin.status = 'rejected'
        else:
            return {'success': False, 'error': '无效的审核操作'}

        plugin.save()
        return {'success': True, 'status': plugin.status, 'notes': notes}
