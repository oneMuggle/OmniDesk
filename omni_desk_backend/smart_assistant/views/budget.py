"""AI 预算与配额接口（方案 5.6）。

- ``GET budget/me/``：当前用户今日状态、用量、上限及来源（任何登录用户）；
- ``GET budget/usage/?days=7``：用量总览（按应用 / 趋势 / 用户排行 / 数字员工），仅智能助手管理员；
- ``GET budget/users/?q=``：个人上限编辑时搜索用户，仅管理员；
- ``budget/policies/``：上限配置增删改查，仅管理员；全员默认只能改不能删。
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q, Sum
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..budget.policy import (
    APP_LABELS,
    app_label,
    app_limits,
    budget_state,
    evaluate,
    soft_percent,
    user_limits,
)
from ..budget.usage import today
from ..models import AgentProfile, LlmBudgetPolicy, LlmUsageDaily
from ..permissions import IsSmartAssistantAdmin

MAX_DAYS = 31
TOP_USERS = 20


def _user_display(user) -> str:
    if user is None:
        return ""
    full = (user.get_full_name() or "").strip() if hasattr(user, "get_full_name") else ""
    return f"{full}（{user.username}）" if full and full != user.username else user.username


class LlmBudgetPolicySerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source="get_scope_display", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True, default="")
    user_display = serializers.SerializerMethodField()
    app_label = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LlmBudgetPolicy
        fields = [
            "id",
            "scope",
            "scope_display",
            "group",
            "group_name",
            "user",
            "user_display",
            "app_name",
            "app_label",
            "daily_token_limit",
            "daily_call_limit",
            "soft_limit_percent",
            "note",
            "updated_by_name",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]
        # 唯一性由 validate 给出中文提示(条件唯一约束不会自动生成校验器)
        validators = []

    def get_user_display(self, obj):
        return _user_display(obj.user)

    def get_app_label(self, obj):
        return app_label(obj.app_name) if obj.app_name else ""

    def get_updated_by_name(self, obj):
        return _user_display(obj.updated_by)

    def validate_soft_limit_percent(self, value):
        if not 1 <= value <= 100:
            raise serializers.ValidationError("只读阈值须在 1–100 之间")
        return value

    def validate(self, attrs):
        instance = self.instance
        scope = attrs.get("scope", instance.scope if instance else None)
        if instance is not None and "scope" in attrs and attrs["scope"] != instance.scope:
            raise serializers.ValidationError({"scope": "作用范围创建后不能修改，请删除后重建"})
        if scope == LlmBudgetPolicy.SCOPE_DEFAULT and instance is None:
            raise serializers.ValidationError({"scope": "全员默认已存在，只能修改"})

        group = attrs.get("group", instance.group if instance else None)
        user = attrs.get("user", instance.user if instance else None)
        app_name = attrs.get("app_name", instance.app_name if instance else "") or ""

        # 按作用范围清理无关字段,并检查必填与唯一
        if scope == LlmBudgetPolicy.SCOPE_GROUP:
            if group is None:
                raise serializers.ValidationError({"group": "请选择用户组"})
            attrs.update(user=None, app_name="")
            clash = LlmBudgetPolicy.objects.filter(scope=scope, group=group)
            field, label = "group", f"用户组「{group.name}」"
        elif scope == LlmBudgetPolicy.SCOPE_USER:
            if user is None:
                raise serializers.ValidationError({"user": "请选择用户"})
            attrs.update(group=None, app_name="")
            clash = LlmBudgetPolicy.objects.filter(scope=scope, user=user)
            field, label = "user", f"用户「{user.username}」"
        elif scope == LlmBudgetPolicy.SCOPE_APP:
            if app_name not in APP_LABELS:
                raise serializers.ValidationError({"app_name": "请选择应用"})
            attrs.update(group=None, user=None, app_name=app_name)
            clash = LlmBudgetPolicy.objects.filter(scope=scope, app_name=app_name)
            field, label = "app_name", f"应用「{app_label(app_name)}」"
        else:
            attrs.update(group=None, user=None, app_name="")
            clash = None
            field = label = ""

        if clash is not None:
            if instance is not None:
                clash = clash.exclude(pk=instance.pk)
            if clash.exists():
                raise serializers.ValidationError({field: f"{label}已有上限配置，请直接修改"})
        return attrs


class LlmBudgetPolicyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsSmartAssistantAdmin]
    serializer_class = LlmBudgetPolicySerializer
    pagination_class = None
    queryset = LlmBudgetPolicy.objects.select_related("group", "user", "updated_by").all()

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        if self.get_object().scope == LlmBudgetPolicy.SCOPE_DEFAULT:
            return Response({"detail": "全员默认不能删除，可把上限改为 0（不限）"}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)


def _sum_row(qs) -> dict:
    row = qs.aggregate(
        tokens=Sum("total_tokens"),
        calls=Sum("calls"),
        failed=Sum("failed_calls"),
        estimated=Sum("estimated_calls"),
        cost=Sum("estimated_cost"),
    )
    return {
        "tokens": row["tokens"] or 0,
        "calls": row["calls"] or 0,
        "failed_calls": row["failed"] or 0,
        "estimated_calls": row["estimated"] or 0,
        "cost": float(row["cost"] or Decimal("0")),
    }


class BudgetViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = LlmUsageDaily.objects.none()

    @action(detail=False, methods=["get"])
    def me(self, request):
        state = budget_state(user_id=request.user.pk, app_name="smart_assistant", include_usage=True)
        return Response(state.to_dict())

    @action(detail=False, methods=["get"], permission_classes=[IsSmartAssistantAdmin])
    def users(self, request):
        q = (request.query_params.get("q") or "").strip()
        qs = get_user_model().objects.filter(is_active=True)
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
        users = qs.order_by("username")[:20]
        return Response([{"id": u.pk, "label": _user_display(u)} for u in users])

    @action(detail=False, methods=["get"], permission_classes=[IsSmartAssistantAdmin])
    def usage(self, request):
        try:
            days = int(request.query_params.get("days", 7))
        except (TypeError, ValueError):
            days = 7
        days = max(1, min(MAX_DAYS, days))
        day = today()
        soft = soft_percent()
        today_qs = LlmUsageDaily.objects.filter(date=day)

        # 今日按应用
        app_names = sorted(set(APP_LABELS) | set(today_qs.values_list("app_name", flat=True)))
        apps = []
        for name in app_names:
            totals = _sum_row(today_qs.filter(app_name=name))
            part = evaluate({"tokens": totals["tokens"], "calls": totals["calls"]}, app_limits(name), soft)
            apps.append({"app_name": name, "app_label": app_label(name), **totals, **part.to_dict()})

        # 近 N 天趋势
        start = day - timedelta(days=days - 1)
        by_date = {
            row["date"]: row
            for row in LlmUsageDaily.objects.filter(date__gte=start, date__lte=day)
            .values("date")
            .annotate(
                tokens=Sum("total_tokens"),
                calls=Sum("calls"),
                estimated=Sum("estimated_calls"),
                cost=Sum("estimated_cost"),
            )
        }
        daily = []
        for offset in range(days):
            d = start + timedelta(days=offset)
            row = by_date.get(d) or {}
            daily.append(
                {
                    "date": d.isoformat(),
                    "tokens": row.get("tokens") or 0,
                    "calls": row.get("calls") or 0,
                    "estimated_calls": row.get("estimated") or 0,
                    "cost": float(row.get("cost") or 0),
                }
            )

        # 今日用户排行(不含数字员工)
        user_rows = list(
            today_qs.filter(staff_key="", user_key__gt=0)
            .values("user_key")
            .annotate(tokens=Sum("total_tokens"), calls=Sum("calls"))
            .order_by("-tokens", "-calls")[:TOP_USERS]
        )
        user_map = get_user_model().objects.in_bulk([r["user_key"] for r in user_rows])
        top_users = []
        for row in user_rows:
            user = user_map.get(row["user_key"])
            usage = {"tokens": row["tokens"] or 0, "calls": row["calls"] or 0}
            part = evaluate(usage, user_limits(row["user_key"]), soft)
            top_users.append({"user_id": row["user_key"], "user_display": _user_display(user), **part.to_dict()})

        # 今日数字员工
        staff_names = dict(AgentProfile.objects.values_list("key", "name"))
        staff = [
            {
                "staff_key": row["staff_key"],
                "name": staff_names.get(row["staff_key"], row["staff_key"]),
                "tokens": row["tokens"] or 0,
                "calls": row["calls"] or 0,
            }
            for row in today_qs.exclude(staff_key="")
            .values("staff_key")
            .annotate(tokens=Sum("total_tokens"), calls=Sum("calls"))
            .order_by("-tokens")
        ]

        totals = _sum_row(today_qs)
        unattributed = _sum_row(today_qs.filter(user_key=0, staff_key=""))
        return Response(
            {
                "date": day.isoformat(),
                "days": days,
                "soft_percent": soft,
                "has_limits": LlmBudgetPolicy.objects.filter(
                    Q(daily_token_limit__gt=0) | Q(daily_call_limit__gt=0)
                ).exists(),
                "totals": {
                    **totals,
                    "estimated_ratio": round(totals["estimated_calls"] / totals["calls"], 3) if totals["calls"] else 0,
                    "unattributed_tokens": unattributed["tokens"],
                },
                "apps": apps,
                "daily": daily,
                "top_users": top_users,
                "staff": staff,
                "groups": list(Group.objects.order_by("name").values("id", "name")),
                "app_choices": [{"value": k, "label": v} for k, v in APP_LABELS.items()],
            }
        )
