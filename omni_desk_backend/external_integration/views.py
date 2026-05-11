import json
import logging
import os
import tempfile
import zipfile
from pathlib import Path

import requests
from django.conf import settings
from rest_framework import viewsets, permissions, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .models import ExternalLink, IntegrationService, Plugin, PluginVersion, PluginCallLog
from .serializers import (
    ExternalLinkSerializer, IntegrationServiceSerializer,
    PluginSerializer, PluginVersionSerializer, PluginUploadSerializer,
)
from .plugin_loader import (
    compute_file_hash, extract_plugin_zip, validate_manifest,
)
from .plugin_sandbox import execute_plugin_safely

logger = logging.getLogger(__name__)


class ExternalLinkViewSet(viewsets.ModelViewSet):
    """外链 CRUD + SSO token 端点"""
    serializer_class = ExternalLinkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ExternalLink.objects.filter(is_active=True).order_by('category', 'sort_order', 'name')

    def list(self, request, *args, **kwargs):
        """返回按分类分组的外链列表"""
        queryset = self.get_queryset()
        groups = {}
        for link in queryset:
            if link.category not in groups:
                groups[link.category] = []
            groups[link.category].append(ExternalLinkSerializer(link).data)

        result = [
            {'category': cat, 'links': links}
            for cat, links in sorted(groups.items())
        ]
        return Response(result)

    @action(detail=True, methods=['post'])
    def sso_token(self, request, pk=None):
        """生成 SSO 跳转 token"""
        link = self.get_object()
        if not link.sso_enabled or not link.sso_token_endpoint:
            return Response(
                {'error': '此链接未启用 SSO'},
                status=status.HTTP_400_BAD_REQUEST
            )
        token = f'sso_placeholder_{link.id}'
        redirect_url = f'{link.url}?token={token}'
        return Response({'redirect_url': redirect_url})


class IntegrationServiceViewSet(viewsets.ModelViewSet):
    """集成服务 CRUD + iframe 嵌入 + API 代理"""
    serializer_class = IntegrationServiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'slug'

    def get_queryset(self):
        return IntegrationService.objects.filter(is_active=True)

    @action(detail=True, methods=['get'])
    def embed(self, request, slug=None):
        """获取 iframe 嵌入 URL"""
        service = self.get_object()
        if service.integration_type != 'iframe':
            return Response(
                {'error': '此服务不支持 iframe 嵌入'},
                status=status.HTTP_400_BAD_REQUEST
            )
        embed_url = f'{service.endpoint_url}/{service.embed_path}'.rstrip('/')
        return Response({'embed_url': embed_url, 'name': service.name})

    @action(detail=True, methods=['post'])
    def proxy(self, request, slug=None):
        """API 代理调用（转发 POST 请求到外部服务）"""
        service = self.get_object()
        if service.integration_type != 'api':
            return Response(
                {'error': '此服务不支持 API 代理'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            headers = {}
            if service.api_key:
                headers['Authorization'] = f'Bearer {service.api_key}'
            resp = requests.post(
                service.endpoint_url,
                json=request.data,
                headers=headers,
                timeout=30,
            )
            return Response(resp.json(), status=resp.status_code)
        except requests.exceptions.Timeout:
            return Response({'error': '外部服务响应超时'}, status=status.HTTP_504_GATEWAY_TIMEOUT)
        except requests.exceptions.ConnectionError:
            return Response({'error': '无法连接到外部服务'}, status=status.HTTP_502_BAD_GATEWAY)


class PluginViewSet(viewsets.ModelViewSet):
    """插件 CRUD + 上传 + 审核 + 执行"""
    queryset = Plugin.objects.all().prefetch_related('versions')
    serializer_class = PluginSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    @action(detail=False, methods=['get'])
    def template(self, request):
        """返回插件开发模板信息"""
        templates = [
            {
                'language': 'C',
                'files': ['main.c', 'plugin_sdk.h'],
                'description': 'C 语言插件模板，使用 stdin/stdout JSON 协议',
            },
            {
                'language': 'C++',
                'files': ['main.cpp', 'plugin_sdk.hpp'],
                'description': 'C++ 语言插件模板',
            },
            {
                'language': 'Fortran',
                'files': ['main.f90', 'plugin_sdk.f90'],
                'description': 'Fortran 插件模板',
            },
            {
                'language': 'Python',
                'files': ['main.py', 'plugin_sdk.py'],
                'description': 'Python 语言插件模板',
            },
            {
                'language': 'Go',
                'files': ['main.go', 'go.mod'],
                'description': 'Go 语言插件模板',
            },
            {
                'language': 'Rust',
                'files': ['main.rs', 'Cargo.toml'],
                'description': 'Rust 语言插件模板',
            },
        ]
        return Response({'templates': templates})

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload_version(self, request, id=None):
        """上传插件新版本"""
        plugin = self.get_object()
        serializer = PluginUploadSerializer(request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = serializer.validated_data['file']
        file_hash = compute_file_hash(uploaded_file)

        # 检查重复版本
        if PluginVersion.objects.filter(plugin=plugin, file_hash=file_hash).exists():
            return Response({'error': '该版本已上传过'}, status=status.HTTP_409_CONFLICT)

        # 保存文件
        version_obj = PluginVersion.objects.create(
            plugin=plugin,
            version=request.data.get('version', '1.0.0'),
            upload_file=uploaded_file,
            file_hash=file_hash,
            uploaded_by=request.user,
        )

        # 尝试读取 manifest.json
        try:
            with zipfile.ZipFile(version_obj.upload_file.path, 'r') as zf:
                if 'manifest.json' in zf.namelist():
                    manifest_data = json.loads(zf.read('manifest.json'))
                    validate_manifest(manifest_data)
                    version_obj.manifest = manifest_data
                    version_obj.save()
        except Exception as e:
            logger.warning('插件 manifest 解析失败: %s', e)

        return Response(
            {'id': version_obj.id, 'version': version_obj.version, 'file_hash': file_hash},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def execute(self, request, id=None):
        """执行插件功能"""
        plugin = self.get_object()
        active_version = plugin.versions.filter(is_active=True).first()
        if not active_version:
            return Response({'error': '没有已激活的插件版本'}, status=status.HTTP_400_BAD_REQUEST)

        # 解压并执行
        try:
            tmp_dir = extract_plugin_zip(active_version.upload_file)
            manifest = active_version.manifest or {'entry_point': 'executable', 'timeout_seconds': 30}
            result = execute_plugin_safely(tmp_dir, manifest, request.data)

            # 记录调用日志
            PluginCallLog.objects.create(
                plugin_version=active_version,
                user=request.user,
                method='execute',
                args_summary=str(request.data)[:500],
                status='success' if result['success'] else 'error',
                execution_time_ms=result.get('execution_time_ms'),
                error_message=result.get('error'),
            )

            return Response(result)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def review(self, request, id=None):
        """审核插件"""
        plugin = self.get_object()
        action_type = request.data.get('action')  # 'approve' or 'reject'
        notes = request.data.get('notes', '')

        if action_type == 'approve':
            plugin.status = 'approved'
        elif action_type == 'reject':
            plugin.status = 'rejected'
        else:
            return Response({'error': '无效的审核操作'}, status=status.HTTP_400_BAD_REQUEST)

        plugin.save()
        return Response({'status': plugin.status, 'notes': notes})

    @action(detail=True, methods=['get'])
    def logs(self, request, id=None):
        """查看插件调用日志"""
        plugin = self.get_object()
        logs = PluginCallLog.objects.filter(plugin_version__plugin=plugin)[:50]
        data = [
            {
                'user': log.user.username if log.user else None,
                'status': log.status,
                'execution_time_ms': log.execution_time_ms,
                'error_message': log.error_message,
                'created_at': log.created_at,
            }
            for log in logs
        ]
        return Response(data)


class PluginTemplateView(viewsets.ViewSet):
    """提供多语言 SDK 模板下载"""
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """返回可用模板列表"""
        template_dir = Path(__file__).parent / 'templates' / 'sdk'
        templates = []
        for lang_dir in template_dir.iterdir():
            if lang_dir.is_dir():
                files = [f.name for f in lang_dir.iterdir() if f.is_file()]
                templates.append({
                    'language': lang_dir.name,
                    'files': files,
                })
        return Response({'templates': templates})
