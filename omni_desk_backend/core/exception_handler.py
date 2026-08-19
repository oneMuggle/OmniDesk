"""全局 DRF EXCEPTION_HANDLER(P1-8)。

DRF 默认 exception_handler 把所有非 2xx 都包装成 ``{"detail": ...}``,
但不携带:

1. ``request_id`` — 前端发请求带 X-Request-ID,响应丢失会让事故现场难定位
2. 500 时的堆栈 — 默认仅记 'Internal server error.',运维需要 stack 才知道哪个 view 崩了

本 handler 在默认行为之上:

- 始终注入 ``request_id``(从 ``request_id_var`` ContextVar 取)
- 仅对 5xx:把 stack 写进 logger.error(exc_info) 与 response body 的
  ``debug`` 字段(只当 settings.DEBUG=True 时才进 response,
  生产环境不下发 stack,避免泄漏内部路径与第三方调用)
- 4xx/3xx 行为保持 DRF 原生包装,只追加 request_id

不在本 handler 范围内(其它模块做):
- 401/403/404 的具体文案(由各 view 决定)
- 5xx 是否重试 / 降级(由前端 ErrorBoundary 兜底)
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

from django.conf import settings
from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

from observability.context import request_id_var

logger = logging.getLogger(__name__)


def omnidesk_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF EXCEPTION_HANDLER — 全局异常出口。

    Args:
        exc: 抛出的异常实例。
        context: DRF 传入的 context 字典,通常含 ``view`` / ``request`` / ``args`` / ``kwargs``。

    Returns:
        DRF Response 实例(已注入 request_id);若异常属于 Django 已知但
        非 DRF APIException 的(如 ``Http404``)→ 返回 None 让 Django 兜底。
    """
    response = drf_default_handler(exc, context)

    # DRF 默认 handler 只识别 APIException 与 (NotAuthenticated/AuthenticationFailed)。
    # 裸 RuntimeError/KeyError 等 → 返回 None,我们兜底生成 500 response。
    if response is None:
        if isinstance(exc, Http404):
            return None  # 让 Django 自身兜底
        response = Response(
            {"detail": "Internal server error."},
            status=500,
        )

    # 1. 注入 request_id(任何 status 都加,便于客户端关联日志)
    rid = request_id_var.get()
    if rid:
        if isinstance(response.data, dict):
            response.data["request_id"] = rid
        else:
            response.data = {"detail": response.data, "request_id": rid}

    # 2. 5xx:写日志 + 仅 DEBUG 下发 stack
    status_code = getattr(response, "status_code", 500)
    if status_code >= 500:
        view = context.get("view")
        view_name = f"{view.__class__.__module__}.{view.__class__.__name__}" if view else "unknown"
        # LOG014:此函数本身就是 DRF 的 EXCEPTION_HANDLER 入口,
        # 进入时 DRF 已捕获原始异常,我们拿到的 `exc` 是已脱离 except 块的对象。
        # 此处显式传 exc_info=True 让 logger 输出完整堆栈,是设计意图。
        logger.error(
            "unhandled exception in %s (status=%s, request_id=%s): %s",
            view_name,
            status_code,
            rid,
            exc,
            exc_info=True,  # noqa: LOG014
        )
        if settings.DEBUG and isinstance(response.data, dict):
            response.data["debug"] = {
                "type": type(exc).__name__,
                # 不能用 format_exc():它读 sys.exc_info(),但 handler 常被直接调用
                # (测试/外部调用)或异常对象传入时已脱离 except 块,此时返回 "NoneType: None"。
                # 用显式传入的 exc 对象重构 stack,任何路径都拿到真实调用栈。
                "stack": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).splitlines()[-20:],
            }

    return response
