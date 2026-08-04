"""events.services.swap_service — 换班申请业务逻辑

原 events/views/swap.py 的 perform_create / accept / reject / cancel 内部
逻辑抽到这里,ViewSet 改为薄包装。本模块不依赖 DRF Request,任何调用方
(工具/HTTP/CLI)都可复用。

调用方需捕获本模块定义的 3 种异常:
- SwapServiceError: 业务错误(目标人不存在 / 排班不存在 / 状态非法)
- SwapPermissionError: 权限错误(用户没关联 personnel / 不是接收方/申请方)
- SwapNotFoundError: swap_id 不存在

ViewSet 转换为:
- SwapPermissionError → DRF PermissionDenied(403)
- SwapNotFoundError → 404
- SwapServiceError → DRF ValidationError(400) 或 409
"""

from __future__ import annotations

from django.utils import timezone  # noqa: F401
from django.db import transaction  # noqa: F401


class SwapServiceError(Exception):
    """业务错误(非用户/权限),由调用方转为 HTTP 400/409。"""


class SwapPermissionError(Exception):
    """权限错误(用户没关联 personnel / 不是接收方/申请方)。"""


class SwapNotFoundError(Exception):
    """swap_id 不存在。"""
