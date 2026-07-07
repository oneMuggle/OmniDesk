import logging

from django.http import JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from users.permissions import IsAdminOrReadOnly

from .client import RagflowClient, RagflowClientError
from .models import RagflowConfig
from .serializers import RagflowConfigSerializer

logger = logging.getLogger(__name__)


class RagflowConfigViewSet(viewsets.ModelViewSet):
    queryset = RagflowConfig.objects.all()
    serializer_class = RagflowConfigSerializer
    permission_classes = [IsAdminOrReadOnly]

    def _get_client(self, config: RagflowConfig) -> RagflowClient:
        """根据配置创建 RAGFlow 客户端实例。"""
        return RagflowClient(
            api_endpoint=config.api_endpoint,
            api_key=config.api_key or "",
        )

    @action(detail=True, methods=["post"])
    def query(self, request, pk=None):
        """使用 RAGFlow Chat API 进行问答。

        需要配置 chat_id（Chat Assistant ID）。
        """
        config = self.get_object()
        if not config.is_active:
            return Response({"detail": "Ragflow 配置未激活。"}, status=status.HTTP_400_BAD_REQUEST)

        if not config.chat_id:
            return Response(
                {"detail": "未配置 Chat Assistant ID。请先在 RAGFlow 中创建 Chat Assistant 并填入 chat_id。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = request.data.get("question")
        conversation_id = request.data.get("conversation_id")

        if not question:
            return Response({"detail": "缺少查询问题。"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = self._get_client(config)
            kwargs = {}
            if conversation_id:
                kwargs["conversation_id"] = conversation_id

            result = client.chat_completion(
                chat_id=config.chat_id,
                question=question,
                **kwargs,
            )

            return Response(result, status=status.HTTP_200_OK)
        except RagflowClientError as e:
            logger.error("RAGFlow Chat API 调用失败: %s", e)
            return Response({"detail": f"Ragflow API 请求失败: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["get"])
    def health_check(self, request, pk=None):
        """测试 RAGFlow 连接是否正常。"""
        config = self.get_object()
        try:
            client = self._get_client(config)
            result = client.health_check()
            if result["status"] == "ok":
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error("RAGFlow 健康检查失败: %s", e)
            return Response(
                {"status": "error", "message": f"健康检查异常: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def list_datasets(self, request, pk=None):
        """列出 RAGFlow 上的所有数据集。"""
        config = self.get_object()
        try:
            client = self._get_client(config)
            datasets = client.list_datasets()
            return Response({"data": datasets}, status=status.HTTP_200_OK)
        except RagflowClientError as e:
            logger.error("RAGFlow 列出数据集失败: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["get"])
    def list_chats(self, request, pk=None):
        """列出 RAGFlow 上的所有聊天助手。"""
        config = self.get_object()
        try:
            client = self._get_client(config)
            chats = client.list_chats()
            return Response({"data": chats}, status=status.HTTP_200_OK)
        except RagflowClientError as e:
            logger.error("RAGFlow 列出聊天助手失败: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def ragflow_configs_view(request):
    """
    一个简单的视图，返回一个固定的 JSON 响应。
    """
    return JsonResponse({"status": "ok"})
