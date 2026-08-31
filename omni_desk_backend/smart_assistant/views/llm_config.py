import requests as http_requests
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from ..models import LlmEndpoint, LlmAppConfig
from ..ssrf import UnsafeEndpointError, safe_request, validate_endpoint_url
from ..serializers import (
    LlmEndpointSerializer,
    LlmEndpointCreateSerializer,
    LlmAppConfigSerializer,
    LlmAppConfigCreateSerializer,
)


def _validate_probe_url(api_endpoint):
    return validate_endpoint_url(api_endpoint)


def _safe_models_url(api_endpoint):
    return _models_url(_validate_probe_url(api_endpoint))


def _models_url(api_endpoint):
    """由端点基础地址拼出上游 /v1/models URL.

    兼容两种填写习惯:https://host 或 https://host/v1 都只拼一次 /v1/models。
    """
    base = api_endpoint.rstrip("/")
    if base.lower().endswith("/models"):
        base = base[: -len("/models")]
    if base.lower().endswith("/v1"):
        base = base[: -len("/v1")]
    return f"{base}/v1/models"


class LlmEndpointViewSet(viewsets.ModelViewSet):
    """LLM API 端点管理：CRUD + fetch-models"""

    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return LlmEndpointCreateSerializer
        return LlmEndpointSerializer

    def get_queryset(self):
        return LlmEndpoint.objects.all().order_by("-created_at")

    def perform_create(self, serializer):
        instance = serializer.save()
        if instance.is_active:
            LlmEndpoint.objects.exclude(id=instance.id).update(is_active=False)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.is_active:
            LlmEndpoint.objects.exclude(id=instance.id).update(is_active=False)

    @action(detail=True, methods=["post"], url_path="fetch-models")
    def fetch_models(self, request, pk=None):
        """根据端点配置调用上游 /v1/models 获取可用模型列表"""
        endpoint = self.get_object()
        api_key = endpoint.api_key

        try:
            resp = safe_request(
                    "GET",
                    _safe_models_url(endpoint.api_endpoint),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10,
                allow_redirects=False,
            )
            if isinstance(resp.status_code, int) and 300 <= resp.status_code < 400:
                return Response(
                    {"error": "上游重定向被安全策略拒绝"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            resp.raise_for_status()
            data = resp.json()

            raw_models = data.get("data", [])
            models = sorted([m["id"] for m in raw_models if "id" in m])

            return Response(
                {
                    "models": models,
                    "count": len(models),
                }
            )
        except UnsafeEndpointError:
            return Response({"error": "端点地址不安全，无法发起请求。"}, status=status.HTTP_400_BAD_REQUEST)
        except http_requests.exceptions.Timeout:
            return Response(
                {"error": "请求超时，请检查端点是否可达"},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except http_requests.exceptions.HTTPError:
            return Response({"error": "上游 API 请求失败。"}, status=status.HTTP_502_BAD_GATEWAY)
        except http_requests.exceptions.ConnectionError:
            return Response(
                {"error": "无法连接到指定端点，请检查网络或端点地址"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except (ValueError, TypeError):
            return Response({"error": "上游响应格式无效。"}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            return Response({"error": "获取模型列表失败。"}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=["post"], url_path="test-endpoint")
    def test_endpoint(self, request, pk=None):
        """测试端点是否可达且认证是否有效"""
        endpoint = self.get_object()
        api_key = endpoint.api_key

        try:
            resp = safe_request(
                    "GET",
                    _safe_models_url(endpoint.api_endpoint),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10,
                allow_redirects=False,
            )
            if isinstance(resp.status_code, int) and 300 <= resp.status_code < 400:
                return Response(
                    {"error": "上游重定向被安全策略拒绝"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            resp.raise_for_status()
            data = resp.json()

            raw_models = data.get("data", [])
            model_count = len([m for m in raw_models if "id" in m])

            return Response(
                {
                    "status": "ok",
                    "message": f"端点连接正常，获取到 {model_count} 个模型",
                    "model_count": model_count,
                }
            )
        except UnsafeEndpointError:
            return Response({"status": "error", "message": "端点地址不安全，无法发起请求。"}, status=status.HTTP_400_BAD_REQUEST)
        except http_requests.exceptions.Timeout:
            return Response(
                {"status": "error", "message": "请求超时，端点不可达"},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except http_requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                return Response(
                    {"status": "auth_error", "message": "认证失败，请检查 API 密钥是否正确"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            return Response({"status": "error", "message": "上游 API 请求失败"}, status=status.HTTP_502_BAD_GATEWAY)
        except http_requests.exceptions.ConnectionError:
            return Response(
                {"status": "connection_error", "message": "无法连接到端点，请检查地址和网络"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except (ValueError, TypeError):
            return Response({"status": "error", "message": "上游响应格式无效"}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            return Response({"status": "error", "message": "端点测试失败"}, status=status.HTTP_502_BAD_GATEWAY)


class LlmAppConfigViewSet(viewsets.ModelViewSet):
    """LLM 应用配置管理：为每个应用分配端点+模型+参数"""

    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return LlmAppConfigCreateSerializer
        return LlmAppConfigSerializer

    def get_queryset(self):
        return LlmAppConfig.objects.select_related("endpoint").all().order_by("-created_at")

    def perform_create(self, serializer):
        instance = serializer.save()
        if instance.is_active:
            LlmAppConfig.objects.filter(app_name=instance.app_name).exclude(id=instance.id).update(is_active=False)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.is_active:
            LlmAppConfig.objects.filter(app_name=instance.app_name).exclude(id=instance.id).update(is_active=False)
