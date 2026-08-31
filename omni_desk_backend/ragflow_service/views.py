from django.http import JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from observability import get_logger
from users.permissions import IsAdminOrReadOnly

from smart_assistant.cache import sanitize_public_sources, sanitize_public_text

from .client import RagflowClient, RagflowClientError
from .models import RagflowConfig
from .serializers import RagflowConfigSerializer

logger = get_logger(__name__, "ragflow_service.views")


def _public_query_result(result):
    if not isinstance(result, dict):
        return {}
    public = {}
    for key in ("answer", "conversation_id"):
        if isinstance(result.get(key), str):
            public[key] = sanitize_public_text(result[key])
    if isinstance(result.get("sources"), list):
        public["sources"] = sanitize_public_sources(result["sources"])
    return public


def _public_items(items, allowed_keys):
    if not isinstance(items, list):
        return []
    return [
        {key: item[key] for key in allowed_keys if key in item}
        for item in items
        if isinstance(item, dict)
    ]


class RagflowConfigViewSet(viewsets.ModelViewSet):
    queryset = RagflowConfig.objects.all()
    serializer_class = RagflowConfigSerializer
    permission_classes = [IsAdminOrReadOnly]

    def _get_client(self, config: RagflowConfig) -> RagflowClient:
        return RagflowClient(api_endpoint=config.api_endpoint, api_key=config.api_key or "")

    @action(detail=True, methods=["post"])
    def query(self, request, pk=None):
        config = self.get_object()
        if not config.is_active:
            return Response({"detail": "Ragflow 配置未激活。"}, status=status.HTTP_400_BAD_REQUEST)
        if not config.chat_id:
            return Response({"detail": "未配置 Chat Assistant ID。请先在 RAGFlow 中创建 Chat Assistant 并填入 chat_id。"}, status=status.HTTP_400_BAD_REQUEST)
        question = request.data.get("question")
        conversation_id = request.data.get("conversation_id")
        if not question:
            return Response({"detail": "缺少查询问题。"}, status=status.HTTP_400_BAD_REQUEST)
        client = self._get_client(config)
        try:
            kwargs = {"conversation_id": conversation_id} if conversation_id else {}
            result = client.chat_completion(chat_id=config.chat_id, question=question, **kwargs)
            return Response(_public_query_result(result), status=status.HTTP_200_OK)
        except RagflowClientError as exc:
            logger.error("RAGFlow Chat API 调用失败: type=%s code=%s", type(exc).__name__, exc.code, exc_info=True)
            return Response({"detail": "Ragflow API 请求失败。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            client.close()

    @action(detail=True, methods=["get"])
    def health_check(self, request, pk=None):
        config = self.get_object()
        client = self._get_client(config)
        try:
            result = client.health_check()
            if result["status"] == "ok":
                return Response({"status": "ok", "message": "连接成功"}, status=status.HTTP_200_OK)
            return Response({"status": "error", "message": "健康检查暂时不可用。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as exc:
            logger.error("RAGFlow 健康检查失败: type=%s", type(exc).__name__)
            return Response({"status": "error", "message": "健康检查暂时不可用。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            client.close()

    @action(detail=True, methods=["get"])
    def list_datasets(self, request, pk=None):
        config = self.get_object()
        client = self._get_client(config)
        try:
            datasets = client.list_datasets()
            return Response({"data": _public_items(datasets, ("id", "name"))}, status=status.HTTP_200_OK)
        except RagflowClientError as exc:
            logger.error("RAGFlow 列出数据集失败: type=%s code=%s", type(exc).__name__, exc.code, exc_info=True)
            return Response({"detail": "RAGFlow 服务暂时不可用。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            client.close()

    @action(detail=True, methods=["get"])
    def list_chats(self, request, pk=None):
        config = self.get_object()
        client = self._get_client(config)
        try:
            chats = client.list_chats()
            return Response({"data": _public_items(chats, ("id", "name", "description"))}, status=status.HTTP_200_OK)
        except RagflowClientError as exc:
            logger.error("RAGFlow 列出聊天助手失败: type=%s code=%s", type(exc).__name__, exc.code, exc_info=True)
            return Response({"detail": "RAGFlow 服务暂时不可用。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            client.close()


def ragflow_configs_view(request):
    return JsonResponse({"status": "ok"})
