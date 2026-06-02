import requests as http_requests
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import LlmEndpoint, LlmAppConfig
from ..serializers import (
    LlmEndpointSerializer,
    LlmEndpointCreateSerializer,
    LlmAppConfigSerializer,
    LlmAppConfigCreateSerializer,
)


class LlmEndpointViewSet(viewsets.ModelViewSet):
    """LLM API 端点管理：CRUD + fetch-models"""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return LlmEndpointCreateSerializer
        return LlmEndpointSerializer

    def get_queryset(self):
        return LlmEndpoint.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        instance = serializer.save()
        if instance.is_active:
            LlmEndpoint.objects.exclude(id=instance.id).update(is_active=False)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.is_active:
            LlmEndpoint.objects.exclude(id=instance.id).update(is_active=False)

    @action(detail=True, methods=['post'], url_path='fetch-models')
    def fetch_models(self, request, pk=None):
        """根据端点配置调用上游 /v1/models 获取可用模型列表"""
        endpoint = self.get_object()
        api_endpoint = endpoint.api_endpoint.rstrip('/')
        api_key = endpoint.api_key

        try:
            resp = http_requests.get(
                f'{api_endpoint}/v1/models',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            raw_models = data.get('data', [])
            models = sorted([m['id'] for m in raw_models if 'id' in m])

            return Response({
                'models': models,
                'count': len(models),
            })
        except http_requests.exceptions.Timeout:
            return Response(
                {'error': '请求超时，请检查端点是否可达'},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except http_requests.exceptions.HTTPError as e:
            return Response(
                {'error': f'上游 API 返回错误: {e.response.status_code} {e.response.text[:200]}'},
                status=e.response.status_code,
            )
        except http_requests.exceptions.ConnectionError:
            return Response(
                {'error': '无法连接到指定端点，请检查网络或端点地址'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            return Response(
                {'error': f'获取模型列表失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=['post'], url_path='test-endpoint')
    def test_endpoint(self, request, pk=None):
        """测试端点是否可达且认证是否有效"""
        endpoint = self.get_object()
        api_endpoint = endpoint.api_endpoint.rstrip('/')
        api_key = endpoint.api_key

        try:
            resp = http_requests.get(
                f'{api_endpoint}/v1/models',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            raw_models = data.get('data', [])
            model_count = len([m for m in raw_models if 'id' in m])

            return Response({
                'status': 'ok',
                'message': f'端点连接正常，获取到 {model_count} 个模型',
                'model_count': model_count,
            })
        except http_requests.exceptions.Timeout:
            return Response(
                {'status': 'error', 'message': '请求超时，端点不可达'},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except http_requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return Response(
                    {'status': 'auth_error', 'message': '认证失败，请检查 API 密钥是否正确'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            return Response(
                {'status': 'error', 'message': f'上游返回 {e.response.status_code}: {e.response.text[:200]}'},
                status=e.response.status_code,
            )
        except http_requests.exceptions.ConnectionError:
            return Response(
                {'status': 'connection_error', 'message': '无法连接到端点，请检查地址和网络'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            return Response(
                {'status': 'error', 'message': f'测试失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LlmAppConfigViewSet(viewsets.ModelViewSet):
    """LLM 应用配置管理：为每个应用分配端点+模型+参数"""
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return LlmAppConfigCreateSerializer
        return LlmAppConfigSerializer

    def get_queryset(self):
        return LlmAppConfig.objects.select_related('endpoint').all().order_by('-created_at')

    def perform_create(self, serializer):
        instance = serializer.save()
        if instance.is_active:
            LlmAppConfig.objects.filter(app_name=instance.app_name).exclude(id=instance.id).update(is_active=False)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.is_active:
            LlmAppConfig.objects.filter(app_name=instance.app_name).exclude(id=instance.id).update(is_active=False)
