"""每日用量累加与查询。"""

from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone


def today():
    return timezone.localdate()


def add_usage(
    *,
    user_id,
    staff_key: str,
    app_name: str,
    calls: int,
    failed_calls: int,
    estimated_calls: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    estimated_cost: Decimal,
) -> None:
    from smart_assistant.models import LlmUsageDaily

    key = {
        "date": today(),
        "user_key": user_id or 0,
        "app_name": app_name or "unknown",
        "staff_key": staff_key or "",
    }
    increments = {
        "calls": F("calls") + calls,
        "failed_calls": F("failed_calls") + failed_calls,
        "estimated_calls": F("estimated_calls") + estimated_calls,
        "prompt_tokens": F("prompt_tokens") + prompt_tokens,
        "completion_tokens": F("completion_tokens") + completion_tokens,
        "total_tokens": F("total_tokens") + total_tokens,
        "estimated_cost": F("estimated_cost") + estimated_cost,
        "updated_at": timezone.now(),
    }
    # 独立保存点：记账失败不会让外层事务（PostgreSQL）进入 aborted 状态
    with transaction.atomic():
        if LlmUsageDaily.objects.filter(**key).update(**increments):
            return
        try:
            with transaction.atomic():
                LlmUsageDaily.objects.create(
                    **key,
                    user_id=user_id,
                    calls=calls,
                    failed_calls=failed_calls,
                    estimated_calls=estimated_calls,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated_cost=estimated_cost,
                )
        except IntegrityError:  # 并发下别人先建了这一行
            LlmUsageDaily.objects.filter(**key).update(**increments)


def _totals(qs) -> dict:
    row = qs.aggregate(tokens=Sum("total_tokens"), calls=Sum("calls"))
    return {"tokens": row["tokens"] or 0, "calls": row["calls"] or 0}


def user_usage_today(user_id) -> dict:
    """用户今日在所有应用上的合计（不含数字员工）。"""
    from smart_assistant.models import LlmUsageDaily

    return _totals(LlmUsageDaily.objects.filter(date=today(), user_key=user_id, staff_key=""))


def app_usage_today(app_name: str) -> dict:
    """应用今日的全部调用（含数字员工）。"""
    from smart_assistant.models import LlmUsageDaily

    return _totals(LlmUsageDaily.objects.filter(date=today(), app_name=app_name))
