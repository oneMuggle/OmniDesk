from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from .chat_stream import handle_stream_chat
from .chat_sync import handle_sync_chat


class SmartChatViewSet(viewsets.ViewSet):
    """智能聊天接口"""

    permission_classes = [IsAuthenticated]
    # 允许 JSON(默认)/multipart/form-data 上传 Office 附件
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def create(self, request):
        """POST /api/smart-assistant/chat/"""
        return handle_sync_chat(self, request)

    @action(detail=False, methods=["post"])
    def stream(self, request):
        """POST /api/smart-assistant/chat/stream/ — SSE 流式响应"""
        return handle_stream_chat(self, request)
