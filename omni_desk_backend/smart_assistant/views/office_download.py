"""smart_assistant/views/office_download.py — 临时生成 .docx 下载端点"""

from __future__ import annotations

import os

from django.conf import settings
from django.http import FileResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..tools_io import _safe_join_under_tmp, resolve_download_token

from observability import get_logger

logger = get_logger(__name__, "smart_assistant")

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _safe_user_id(user) -> int | str | None:
    """提取当前用户的稳定 ID（pk），未登录或匿名返回 None。"""
    if not user or not getattr(user, "is_authenticated", False):
        return None
    pk = getattr(user, "pk", None)
    return pk


class OfficeDownloadView(APIView):
    """返回临时生成的 .docx。token 一次性、10 分钟过期、仅签发者本人可下载。"""

    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        current_user_id = _safe_user_id(request.user)
        resolved = resolve_download_token(token, current_user_id)
        if not resolved:
            return Response({"detail": "链接已失效，请重新生成"}, status=403)
        relative_path, _owner_id = resolved

        # 路径范围校验：解析后必须落在 MEDIA_ROOT/tmp_office/ 内
        full = _safe_join_under_tmp(relative_path)
        if full is None or not full.is_file():
            logger.warning(
                "下载文件路径逃逸或不存在: user=%s rel=%s",
                current_user_id,
                relative_path,
            )
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
                    full.unlink()  # 下载后即删
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
