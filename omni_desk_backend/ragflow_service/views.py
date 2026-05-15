import requests
from django.http import JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from users.permissions import IsAdminOrReadOnly
from rest_framework.response import Response

from .models import RagflowConfig
from .serializers import RagflowConfigSerializer


class RagflowConfigViewSet(viewsets.ModelViewSet):
    queryset = RagflowConfig.objects.all()
    serializer_class = RagflowConfigSerializer
    permission_classes = [IsAdminOrReadOnly]

    @action(detail=True, methods=['post'])
    def query(self, request, pk=None):
        config = self.get_object()
        if not config.is_active:
            return Response({"detail": "Ragflow 配置未激活。"}, status=status.HTTP_400_BAD_REQUEST)

        # 从请求中获取查询参数，例如 `question` 和 `conversation_id`
        question = request.data.get('question')
        conversation_id = request.data.get('conversation_id')

        if not question:
            return Response({"detail": "缺少查询问题。"}, status=status.HTTP_400_BAD_REQUEST)

        # 构造 Ragflow API 请求
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        }

        # 根据 Ragflow 的实际 API 文档调整请求体
        # 假设 Ragflow 的 API 接收 JSON 格式的 { "question": "...", "conversation_id": "..." }
        payload = {
            "question": question,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        try:
            response = requests.post(
                f"{config.api_endpoint}/v1/chat/completions", # 假设 Ragflow 的聊天 API 路径
                headers=headers,
                json=payload
            )
            response.raise_for_status()  # 检查HTTP错误

            return Response(response.json(), status=status.HTTP_200_OK)
        except requests.exceptions.RequestException as e:
            return Response({"detail": f"Ragflow API 请求失败: {e!s}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def ragflow_configs_view(request):
   """
   一个简单的视图，返回一个固定的 JSON 响应。
   """
   return JsonResponse({'status': 'ok'})
