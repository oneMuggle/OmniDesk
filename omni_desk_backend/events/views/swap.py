"""events.views.swap — 换班申请 ViewSet

拆分自原 events/views.py(Phase 3 优化)。包含:
- SwapRequestViewSet: 排班换班申请(两人互认即生效,决策 1C)
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from users.permissions import IsRequester, IsTargetPersonnel

from ..models import ScheduleSwapAuditLog, ScheduleSwapRequest
from ..serializers import (
    SwapRequestCreateSerializer,
    SwapRequestDetailSerializer,
    SwapRequestListSerializer,
    SwapRequestTargetActionSerializer,
)

logger = logging.getLogger(__name__)


class SwapRequestViewSet(viewsets.ModelViewSet):
    """排班换班申请 ViewSet。

    行级权限:三视角(申请方/接收方/HR 知情)。
    - cancel:申请方 (IsRequester)
    - accept/reject:接收方 (IsTargetPersonnel)
    - 其他 list/retrieve:任何登录用户(行级过滤由 get_queryset 完成)
    """

    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("cancel",):
            return [permissions.IsAuthenticated(), IsRequester()]
        if self.action in ("accept", "reject"):
            return [permissions.IsAuthenticated(), IsTargetPersonnel()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        personnel = getattr(user, "personnel", None)
        base = (
            ScheduleSwapRequest.objects.select_related(
                "requester",
                "target_personnel",
                "original_schedule",
                "target_schedule",
                "approver",
            )
            .prefetch_related("audit_logs")
            .order_by("-created_at")
        )
        role = self.request.query_params.get("role", "all")
        if personnel is None:
            return base.none()
        if role == "requester":
            return base.filter(requester=personnel)
        if role == "target":
            return base.filter(target_personnel=personnel)
        return base.filter(Q(requester=personnel) | Q(target_personnel=personnel))

    def get_serializer_class(self):
        if self.action == "list":
            return SwapRequestListSerializer
        if self.action in ("retrieve", "accept", "reject", "cancel"):
            if self.action in ("accept", "reject"):
                return SwapRequestTargetActionSerializer
            return SwapRequestDetailSerializer
        return SwapRequestCreateSerializer

    def perform_create(self, serializer):
        requester = getattr(self.request.user, "personnel", None)
        if requester is None:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("当前用户尚未关联人员档案,请联系 HR")
        ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
        try:
            with transaction.atomic():
                instance = serializer.save(
                    requester=requester,
                    expires_at=timezone.now() + timedelta(hours=ttl),
                    status=ScheduleSwapRequest.STATUS_PENDING,
                )
                instance.full_clean()
        except DjangoValidationError as e:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            raise DRFValidationError(e.message_dict)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """决策 1C:接收方 accept → status=approved,自动调 apply_swap()。"""
        swap = self.get_object()
        if swap.status != ScheduleSwapRequest.STATUS_PENDING:
            return Response(
                {"detail": f"该申请不在 pending 状态(当前:{swap.status}),无法 accept"},
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            old_status = swap.status
            target_user = getattr(swap.target_personnel, "user_account", None)
            swap.apply_swap(approver=target_user)
            ScheduleSwapAuditLog.objects.create(
                swap_request=swap,
                actor=request.user,
                from_status=old_status,
                to_status=swap.status,
                note=request.data.get("target_decision_note", "接收方同意"),
            )
        return Response(SwapRequestDetailSerializer(swap).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """接收方 reject → status=rejected_by_target。"""
        swap = self.get_object()
        if swap.status != ScheduleSwapRequest.STATUS_PENDING:
            return Response(
                {"detail": f"该申请不在 pending 状态(当前:{swap.status})"},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            old_status = swap.status
            swap.status = ScheduleSwapRequest.STATUS_REJECTED
            swap.target_decided_at = timezone.now()
            swap.target_decision_note = request.data.get("target_decision_note", "")
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
                actor=request.user,
                from_status=old_status,
                to_status=swap.status,
                note="接收方拒绝",
            )
        return Response(SwapRequestDetailSerializer(swap).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """申请方 cancel → status=cancelled。"""
        swap = self.get_object()
        if swap.status != ScheduleSwapRequest.STATUS_PENDING:
            return Response(
                {"detail": f"该申请不在 pending 状态(当前:{swap.status})"},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            old_status = swap.status
            swap.status = ScheduleSwapRequest.STATUS_CANCELLED
            swap.save(update_fields=["status", "updated_at"])
            ScheduleSwapAuditLog.objects.create(
                swap_request=swap,
                actor=request.user,
                from_status=old_status,
                to_status=swap.status,
                note="申请方撤销",
            )
        return Response(SwapRequestDetailSerializer(swap).data)
