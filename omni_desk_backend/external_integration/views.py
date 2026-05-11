import requests
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ExternalLink, IntegrationService
from .serializers import ExternalLinkSerializer, IntegrationServiceSerializer


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
