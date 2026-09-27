"""写操作确认 / 取消接口（S3-1）。

- ``POST confirmations/{token}/approve/``：执行写操作。成功返回 200，附带
  ``write_log_id`` / ``reversible`` 供前端显示「撤销」；工具返回冲突类错误时返回 409，
  其他业务失败返回 400。
- ``POST confirmations/{token}/reject/``：取消，token 立即作废。

校验规则见 ``smart_assistant.writes.confirmations``。
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..cache import public_tool_result, sanitize_public_text
from ..writes.confirmations import (
    CONFLICT_ERROR_CODES,
    ConfirmationError,
    execute_confirmed,
    reject,
    result_write_meta,
)


class ConfirmationApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        try:
            tool, tool_result, _ = execute_confirmed(request.user, token)
        except ConfirmationError as exc:
            return Response(exc.as_body(), status=exc.status)
        result = tool_result if isinstance(tool_result, dict) else {}
        if result.get("found") is False or result.get("error"):
            code = result.get("error_code") or "write_failed"
            http_status = status.HTTP_409_CONFLICT if code in CONFLICT_ERROR_CODES else status.HTTP_400_BAD_REQUEST
            detail = sanitize_public_text(result.get("message") or "操作未完成", 200)
            return Response({"detail": detail, "code": code, "tool_used": tool.name}, status=http_status)
        return Response(
            {
                "answer": sanitize_public_text(result.get("summary") or "操作已完成", 300),
                "tool_used": tool.name,
                "tool_result": public_tool_result(result, tool.name),
                "confirmed": True,
                **result_write_meta(result),
            }
        )


class ConfirmationRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        try:
            body = reject(request.user, token)
        except ConfirmationError as exc:
            return Response(exc.as_body(), status=exc.status)
        return Response(body)
