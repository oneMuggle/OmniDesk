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

from events.models import Schedule, ScheduleSwapAuditLog, ScheduleSwapRequest
from personnel.models import Personnel


class SwapServiceError(Exception):
    """业务错误(非用户/权限),由调用方转为 HTTP 400/409。

    Attributes:
        field: 关联字段名(如 "target_personnel" / "requester"),可选。
        ViewSet 据此把错误恢复到 serializer 字段格式:
        {"<field>": "..."} 或 {"detail": "..."}(field 为空时)。
    """

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


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
        # 保留字段名,以便 ViewSet 还原为 serializer 字段格式
        if hasattr(e, "message_dict"):
            field_name, messages = next(iter(e.message_dict.items()))
            raise SwapServiceError(messages[0], field=field_name) from e
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


def accept_swap(*, actor, swap_id: int, note: str = "") -> ScheduleSwapRequest:
    """接收方 accept → apply_swap + audit_log。

    权限:actor.user_account == swap.target_personnel.user_account
    前置状态:swap.status == STATUS_PENDING

    Raises:
        SwapNotFoundError: swap_id 不存在
        SwapPermissionError: actor 不是 target_personnel
        SwapServiceError: swap 不在 pending 状态
    """
    try:
        swap = ScheduleSwapRequest.objects.get(pk=swap_id)
    except ScheduleSwapRequest.DoesNotExist:
        raise SwapNotFoundError(f"换班申请 #{swap_id} 不存在")

    target_user = getattr(swap.target_personnel, "user_account", None)
    if target_user != actor:
        raise SwapPermissionError("仅接收方可以接受换班申请")
    if swap.status != ScheduleSwapRequest.STATUS_PENDING:
        raise SwapServiceError(f"该申请 not in pending 状态(当前:{swap.status}),无法 accept")

    with transaction.atomic():
        old_status = swap.status
        swap.apply_swap(approver=actor)
        ScheduleSwapAuditLog.objects.create(
            swap_request=swap,
            actor=actor,
            from_status=old_status,
            to_status=swap.status,
            note=note or "接收方同意",
        )
    return swap


def reject_swap(*, actor, swap_id: int, note: str = "") -> ScheduleSwapRequest:
    """接收方 reject → status=STATUS_REJECTED + audit_log。

    Raises:
        SwapNotFoundError: swap_id 不存在
        SwapPermissionError: actor 不是 target_personnel
        SwapServiceError: swap 不在 pending 状态
    """
    try:
        swap = ScheduleSwapRequest.objects.get(pk=swap_id)
    except ScheduleSwapRequest.DoesNotExist:
        raise SwapNotFoundError(f"换班申请 #{swap_id} 不存在")

    target_user = getattr(swap.target_personnel, "user_account", None)
    if target_user != actor:
        raise SwapPermissionError("仅接收方可以拒绝换班申请")
    if swap.status != ScheduleSwapRequest.STATUS_PENDING:
        raise SwapServiceError(f"该申请 not in pending 状态(当前:{swap.status})")

    with transaction.atomic():
        old_status = swap.status
        swap.status = ScheduleSwapRequest.STATUS_REJECTED
        swap.target_decided_at = timezone.now()
        swap.target_decision_note = note
        swap.save(
            update_fields=[
                "status",
                "target_decided_at",
                "target_decision_note",
                "updated_at",
            ]
        )
        ScheduleSwapAuditLog.objects.create(
            swap_request=swap,
            actor=actor,
            from_status=old_status,
            to_status=swap.status,
            note="接收方拒绝",
        )
    return swap


def cancel_swap(*, actor, swap_id: int) -> ScheduleSwapRequest:
    """申请方 cancel → status=STATUS_CANCELLED + audit_log。

    Raises:
        SwapNotFoundError: swap_id 不存在
        SwapPermissionError: actor 不是 requester
        SwapServiceError: swap 不在 pending 状态
    """
    try:
        swap = ScheduleSwapRequest.objects.get(pk=swap_id)
    except ScheduleSwapRequest.DoesNotExist:
        raise SwapNotFoundError(f"换班申请 #{swap_id} 不存在")

    requester_user = getattr(swap.requester, "user_account", None)
    if requester_user != actor:
        raise SwapPermissionError("仅申请方可以撤销换班申请")
    if swap.status != ScheduleSwapRequest.STATUS_PENDING:
        raise SwapServiceError(f"该申请 not in pending 状态(当前:{swap.status})")

    with transaction.atomic():
        old_status = swap.status
        swap.status = ScheduleSwapRequest.STATUS_CANCELLED
        swap.save(update_fields=["status", "updated_at"])
        ScheduleSwapAuditLog.objects.create(
            swap_request=swap,
            actor=actor,
            from_status=old_status,
            to_status=swap.status,
            note="申请方撤销",
        )
    return swap
