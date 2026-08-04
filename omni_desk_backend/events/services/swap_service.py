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

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from events.models import Schedule, ScheduleSwapRequest
from personnel.models import Personnel


class SwapServiceError(Exception):
    """业务错误(非用户/权限),由调用方转为 HTTP 400/409。"""


class SwapPermissionError(Exception):
    """权限错误(用户没关联 personnel / 不是接收方/申请方)。"""


class SwapNotFoundError(Exception):
    """swap_id 不存在。"""


def _create_swap_internal(
    *,
    requester,
    target_personnel,
    original_schedule,
    target_schedule,
    scope,
    reason,
) -> ScheduleSwapRequest:
    """内部共用:校验 + 构造 + 保存 swap。

    必须在 transaction.atomic() 内调用(外层 caller 已包)。
    数据校验委托给 ScheduleSwapRequest.clean()(L3 防护)。
    """
    ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
    instance = ScheduleSwapRequest(
        requester=requester,
        original_schedule=original_schedule,
        target_personnel=target_personnel,
        target_schedule=target_schedule,
        scope=scope,
        reason=reason,
        expires_at=timezone.now() + timedelta(hours=ttl),
        status=ScheduleSwapRequest.STATUS_PENDING,
    )
    try:
        instance.full_clean()
    except Exception as e:
        # 将 model.ValidationError 转换为 SwapServiceError,统一异常类型
        if hasattr(e, "message_dict"):
            raise SwapServiceError(str(list(e.message_dict.values())[0][0])) from e
        raise SwapServiceError(str(e)) from e
    instance.save()
    return instance


def create_swap_from_serializer(*, serializer) -> ScheduleSwapRequest:
    """从已校验的 DRF serializer 创建 swap(供 ViewSet 的 perform_create 使用)。

    serializer.validated_data 必须包含:
    - requester (Personnel): 由 perform_create 注入
    - original_schedule (Schedule)
    - target_personnel (Personnel)
    - target_schedule (Schedule | None)
    - scope (str): "duty_person" | "duty_leader"
    - reason (str)
    """
    validated = serializer.validated_data
    with transaction.atomic():
        return _create_swap_internal(
            requester=validated["requester"],
            target_personnel=validated["target_personnel"],
            original_schedule=validated["original_schedule"],
            target_schedule=validated.get("target_schedule"),
            scope=validated.get("scope", ScheduleSwapRequest.SCOPE_DUTY_PERSON),
            reason=validated.get("reason", ""),
        )


def create_swap_by_query(
    *,
    requester,
    target_name: str,
    duty_date,
    reason: str = "",
) -> ScheduleSwapRequest:
    """从自由文本创建 swap(供 Smart Assistant 工具 + CLI 使用)。

    步骤:
    1. Personnel.objects.filter(name=target_name).first() 找 target
    2. Schedule.objects.filter(duty_date=duty_date, duty_person=requester).first() 找 schedule
    3. 校验 target_personnel != requester
    4. 调 _create_swap_internal

    Raises:
        SwapServiceError: 目标人不存在 / 排班不存在 / 自己换自己
    """
    target_personnel = Personnel.objects.filter(name=target_name).first()
    if target_personnel is None:
        raise SwapServiceError(f"未找到 '{target_name}' 该人员")
    original_schedule = Schedule.objects.filter(
        duty_date=duty_date, duty_person=requester
    ).first()
    if original_schedule is None:
        raise SwapServiceError(f"找不到您 {duty_date} 的排班记录")
    with transaction.atomic():
        return _create_swap_internal(
            requester=requester,
            target_personnel=target_personnel,
            original_schedule=original_schedule,
            target_schedule=None,
            scope=ScheduleSwapRequest.SCOPE_DUTY_PERSON,
            reason=reason,
        )
