"""数字员工接口（S4-1）。

- ``agent-profiles/``：管理端（仅智能助手管理员）查看角色、启停、改配额、立即运行、看运行记录。
- ``proposals/``：本人的待确认事项，确认 / 取消（他人的返回 404）。
"""

from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..cache import sanitize_public_text
from ..models import AgentProfile, AgentProposal
from ..permissions import IsSmartAssistantAdmin
from ..staff import proposals as proposal_service
from ..staff.serializers import AgentProfileSerializer, AgentProposalSerializer, AgentRunSerializer
from ..staff.runtime import record_event

RECENT_RUNS = 20
EDITABLE_FIELDS = {"enabled", "daily_llm_quota", "daily_action_quota", "owner"}


class AgentProfileViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    permission_classes = [IsSmartAssistantAdmin]
    serializer_class = AgentProfileSerializer
    queryset = AgentProfile.objects.select_related("owner").order_by("id")
    lookup_field = "key"
    http_method_names = ["get", "patch", "post", "head", "options"]

    def partial_update(self, request, *args, **kwargs):
        unknown = sorted(set(request.data.keys()) - EDITABLE_FIELDS)
        if unknown:
            return Response(
                {"detail": f"不允许修改的字段：{'、'.join(unknown)}", "code": "readonly_field"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile = self.get_object()
        before = {field: getattr(profile, field if field != "owner" else "owner_id") for field in EDITABLE_FIELDS}
        response = super().partial_update(request, *args, **kwargs)
        profile.refresh_from_db()
        after = {field: getattr(profile, field if field != "owner" else "owner_id") for field in EDITABLE_FIELDS}
        changed = {k: {"before": before[k], "after": after[k]} for k in EDITABLE_FIELDS if before[k] != after[k]}
        if changed:
            record_event(profile, "config.changed", user=request.user, changes=changed)
        return response

    @action(detail=True, methods=["post"])
    def run(self, request, key=None):
        from ..tasks import run_agent_profile

        profile = self.get_object()
        if not profile.enabled:
            return Response({"detail": "该角色未启用，请先启用。", "code": "disabled"}, status=status.HTTP_409_CONFLICT)
        run_agent_profile.delay(profile.key, "manual", request.user.pk)
        return Response({"detail": "已提交运行，稍后刷新查看结果。"}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def runs(self, request, key=None):
        profile = self.get_object()
        runs = profile.runs.order_by("-started_at", "-id")[:RECENT_RUNS]
        return Response(AgentRunSerializer(runs, many=True, context={"with_events": True}).data)


class AgentProposalViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AgentProposalSerializer

    def get_queryset(self):
        qs = AgentProposal.objects.filter(user=self.request.user).select_related("profile")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("-created_at", "-id")[:100] if self.action == "list" else qs

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        try:
            proposal, result = proposal_service.approve(request.user, pk)
        except proposal_service.ProposalError as exc:
            return Response(exc.as_body(), status=exc.status)
        log_id = result.get("write_log_id")
        return Response(
            {
                "answer": sanitize_public_text(result.get("summary") or "操作已完成", 300),
                "confirmed": True,
                "write_log_id": log_id if isinstance(log_id, int) else None,
                "reversible": bool(result.get("reversible") and log_id),
                "proposal": AgentProposalSerializer(proposal).data,
            }
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        try:
            proposal = proposal_service.reject(request.user, pk)
        except proposal_service.ProposalError as exc:
            return Response(exc.as_body(), status=exc.status)
        return Response({"cancelled": True, "proposal": AgentProposalSerializer(proposal).data})
