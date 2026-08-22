"""events.views.swap — 换班申请 ViewSet(薄包装,业务逻辑在 services.swap_service)"""

from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.response import Response

from observability import get_logger
from events.services import swap_service
from events.services.swap_service import (
    SwapNotFoundError,
    SwapPermissionError,
    SwapServiceError,
)
from users.permissions import IsRequester, IsTargetPersonnel

from ..models import ScheduleSwapRequest
from ..serializers import (
    SwapRequestCreateSerializer,
    SwapRequestDetailSerializer,
    SwapRequestListSerializer,
    SwapRequestTargetActionSerializer,
)

logger = get_logger(__name__, "events.views.swap")


class SwapRequestViewSet(viewsets.ModelViewSet):
    """排班换班申请 ViewSet(薄包装)。

    业务逻辑(events.services.swap_service)与 HTTP 层分离:
    - perform_create: 调 create_swap_from_serializer
    - accept / reject: 调 accept_swap / reject_swap
    - cancel: 调 cancel_swap
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
        """薄包装:把 serializer 注入 requester 后调 service。"""
        requester = getattr(self.request.user, "personnel", None)
        if requester is None:
            raise PermissionDenied("当前用户尚未关联人员档案,请联系 HR")
        serializer.is_valid(raise_exception=True)
        serializer.validated_data["requester"] = requester
        try:
            instance = swap_service.create_swap_from_serializer(serializer=serializer)
        except SwapPermissionError as e:
            raise PermissionDenied(str(e))
        except SwapServiceError as e:
            # 还原为 serializer 字段格式: {"<field>": "..."}
            error_payload = {e.field: [e.message]} if e.field else {"detail": e.message}
            raise DRFValidationError(error_payload)
        self._swap_instance = instance

    def create(self, request, *args, **kwargs):
        """重写 create:perform_create 走 service,直接返回详情 serializer。"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = getattr(self, "_swap_instance", None)
        if instance is None:
            return Response(
                {"detail": "创建失败:perform_create 未设置 instance"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            SwapRequestDetailSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """接收方 accept。"""
        try:
            swap = swap_service.accept_swap(
                actor=request.user,
                swap_id=pk,
                note=request.data.get("target_decision_note", "接收方同意"),
            )
        except SwapNotFoundError:
            return Response({"detail": "换班申请不存在"}, status=status.HTTP_404_NOT_FOUND)
        except SwapPermissionError as e:
            raise PermissionDenied(str(e))
        except SwapServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(SwapRequestDetailSerializer(swap).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """接收方 reject。"""
        try:
            swap = swap_service.reject_swap(
                actor=request.user,
                swap_id=pk,
                note=request.data.get("target_decision_note", ""),
            )
        except SwapNotFoundError:
            return Response({"detail": "换班申请不存在"}, status=status.HTTP_404_NOT_FOUND)
        except SwapPermissionError as e:
            raise PermissionDenied(str(e))
        except SwapServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(SwapRequestDetailSerializer(swap).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """申请方 cancel。"""
        try:
            swap = swap_service.cancel_swap(actor=request.user, swap_id=pk)
        except SwapNotFoundError:
            return Response({"detail": "换班申请不存在"}, status=status.HTTP_404_NOT_FOUND)
        except SwapPermissionError as e:
            raise PermissionDenied(str(e))
        except SwapServiceError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        return Response(SwapRequestDetailSerializer(swap).data)
