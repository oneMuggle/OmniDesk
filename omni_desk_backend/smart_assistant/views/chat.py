from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from .chat_stream import handle_stream_chat
from .chat_sync import handle_sync_chat
from .conversation_manager import extract_attachment, inject_attachment


class SmartChatViewSet(viewsets.ViewSet):
    """智能聊天接口"""

    permission_classes = [IsAuthenticated]
    # 允许 JSON(默认)/multipart/form-data 上传 Office 附件
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _extract_attachment(self, request):
        """校验并抽取附件。返回 (doc_dict, None) 或 (None, error_response)。

        逻辑已下移 conversation_manager,薄壳仅原样转发。
        """
        return extract_attachment(request)

    def _inject_attachment(self, conversation_history, doc_dict, conversation_id):
        """把附件内容注入历史并写短时缓存。

        逻辑已下移 conversation_manager,薄壳仅原样转发。
        """
        return inject_attachment(conversation_history, doc_dict, conversation_id)

    def create(self, request):
        """POST /api/smart-assistant/chat/"""
        return handle_sync_chat(self, request)

    @action(detail=False, methods=["post"])
    def stream(self, request):
        """POST /api/smart-assistant/chat/stream/ — SSE 流式响应"""
        return handle_stream_chat(self, request)
