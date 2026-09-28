"""数字员工接口的序列化器（S4-1）。"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from smart_assistant.models import AgentProfile, AgentProposal, AgentRun, AgentRunEvent

from ..writes.preview import public_preview, preview_summary
from .runtime import usage_today

MAX_QUOTA = 100000


class AgentRunEventSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = AgentRunEvent
        fields = ["id", "event_type", "user", "user_name", "payload", "created_at"]

    def get_user_name(self, obj):
        return obj.user.get_username() if obj.user_id else None


class AgentRunSerializer(serializers.ModelSerializer):
    events = serializers.SerializerMethodField()

    class Meta:
        model = AgentRun
        fields = ["id", "trigger", "status", "started_at", "finished_at", "stats", "error", "events"]

    def get_events(self, obj):
        if not self.context.get("with_events"):
            return None
        return AgentRunEventSerializer(obj.events.select_related("user").order_by("id")[:200], many=True).data


class AgentProfileSerializer(serializers.ModelSerializer):
    """管理端：只允许修改启停、配额与负责人，其余字段只读。"""

    owner = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.filter(is_active=True), allow_null=True, required=False
    )
    owner_name = serializers.SerializerMethodField()
    usage_today = serializers.SerializerMethodField()
    last_run = serializers.SerializerMethodField()
    daily_llm_quota = serializers.IntegerField(min_value=0, max_value=MAX_QUOTA, required=False)
    daily_action_quota = serializers.IntegerField(min_value=0, max_value=MAX_QUOTA, required=False)

    class Meta:
        model = AgentProfile
        fields = [
            "key",
            "name",
            "description",
            "toolsets",
            "data_scope",
            "trigger",
            "schedule_label",
            "enabled",
            "owner",
            "owner_name",
            "daily_llm_quota",
            "daily_action_quota",
            "usage_today",
            "last_run",
            "updated_at",
        ]
        read_only_fields = [
            "key",
            "name",
            "description",
            "toolsets",
            "data_scope",
            "trigger",
            "schedule_label",
            "updated_at",
        ]

    def get_owner_name(self, obj):
        return obj.owner.get_username() if obj.owner_id else None

    def get_usage_today(self, obj):
        return usage_today(obj)

    def get_last_run(self, obj):
        run = obj.runs.order_by("-started_at", "-id").first()
        return AgentRunSerializer(run).data if run else None


class AgentProposalSerializer(serializers.ModelSerializer):
    """本人待确认事项：只公开过滤后的预览，不返回内部 fields。"""

    profile_name = serializers.CharField(source="profile.name", read_only=True)
    preview = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    result_message = serializers.SerializerMethodField()

    class Meta:
        model = AgentProposal
        fields = [
            "id",
            "profile_name",
            "kind",
            "title",
            "preview",
            "summary",
            "status",
            "expires_at",
            "decided_at",
            "result_message",
            "created_at",
        ]

    def get_preview(self, obj):
        return public_preview(obj.preview)

    def get_summary(self, obj):
        preview = public_preview(obj.preview)
        return preview_summary(preview) if preview else obj.title

    def get_result_message(self, obj):
        result = obj.result or {}
        return (result.get("summary") or result.get("message") or "")[:300] or None
