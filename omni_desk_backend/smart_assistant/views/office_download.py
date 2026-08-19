"""smart_assistant/views/office_download.py — 临时生成 .docx 下载端点"""

from __future__ import annotations

import os

from django.conf import settings
from django.http import FileResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..tools_io import resolve_download_token

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class OfficeDownloadView(APIView):
    """返回临时生成的 .docx。token 一次性、10 分钟过期。"""

    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        relative_path = resolve_download_token(token)
        if not relative_path:
            return Response({"detail": "链接已失效，请重新生成"}, status=403)
        full = os.path.join(settings.MEDIA_ROOT or "", relative_path)
        if not os.path.isfile(full):
            logger.warning("下载文件不存在: %s", relative_path)
            return Response({"detail": "文件不存在"}, status=404)
        try:
            f = open(full, "rb")  # noqa: SIM115 — 文件句柄在 FileResponse 响应结束后由 _cleanup 关闭
        except OSError as exc:
            logger.exception("打开下载文件失败: %s", full)
            return Response({"detail": "文件读取失败"}, status=500)

        def _cleanup():
            try:
                f.close()
            finally:
                try:
                    os.remove(full)  # 下载后即删
                except OSError:
                    pass

        resp = FileResponse(
            f,
            content_type=DOCX_MIME,
            as_attachment=True,
            filename=os.path.basename(relative_path),
        )
        resp.close = _cleanup
        return resp
