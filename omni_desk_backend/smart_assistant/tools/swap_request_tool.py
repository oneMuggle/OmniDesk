"""smart_assistant/tools/swap_request_tool.py — 换班申请工具(confirm-replay 框架接入)

三个工具类:
- SwapRequestQueryTool(read): 查询当前用户相关的换班申请
- SwapRequestCreateTool(write, require_confirmation=True): 发起换班申请
- SwapRequestDecideTool(write, require_confirmation=True): 接收方决策(accept/reject)或申请方撤销(cancel)

业务逻辑复用 events.SwapRequestViewSet + ScheduleSwapRequest 模型。
工具层只负责:
1. 自然语言解析(query → 结构化参数)
2. dry_run 模式下返回 draft(供 confirm-replay 框架存缓存)
3. confirmed 模式下调用业务逻辑落库

上游依赖:
- confirm-replay 框架(Phase A-D):apply_pre_execute_hooks + set/get/clear_confirmation_draft
- 前端 QuickAssistant:识别 awaiting_confirmation 信号 → 弹 Modal.confirm → 二次请求带 confirm_token
"""

import logging
from datetime import date, datetime

from django.db.models import Q
from events.models import Schedule, ScheduleSwapRequest
from personnel.models import Personnel

from ..extractors.swap_extractor import extract_create_params
from events.services.swap_service import (
    SwapServiceError,
    SwapPermissionError,
    create_swap_by_query,
)
from .base import BaseTool

logger = logging.getLogger(__name__)


def _parse_date_string(s: str) -> date | None:
    """鲁棒地解析日期字符串,失败返回 None。

    接受格式:
    - "2026-08-12"(ISO)
    - "08-12"(MM-DD,默认当年)
    """
    if not s:
        return None
    s = s.strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(s, "%m-%d").date().replace(year=date.today().year)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 工具 1: 查询换班申请
# ---------------------------------------------------------------------------


class SwapRequestQueryTool(BaseTool):
    """查询当前用户相关的换班申请(发起的 + 接收的)"""

    name = "swap_request_query"
    description = "查询换班申请状态(我发起的 / 我收到的)"
    intent_type = "swap_request_query"
    risk_level = "read"

    def execute(self, query=None, context=None, **kwargs) -> dict:
        """查询当前用户相关的换班申请"""
        user = getattr(context, "user", None) if context else None
        if user is None:
            return {"found": False, "message": "未登录用户无法查询换班申请"}

        personnel = getattr(user, "personnel", None)
        if personnel is None:
            return {"found": False, "message": "当前用户未关联人员档案"}

        # 查当前用户作为 requester 或 target_personnel 的所有申请
        swaps = (
            ScheduleSwapRequest.objects.filter(Q(requester=personnel) | Q(target_personnel=personnel))
            .select_related("requester", "target_personnel", "original_schedule", "target_schedule")
            .order_by("-created_at")[:10]  # 最多返回 10 条
        )

        if not swaps.exists():
            return {"found": False, "message": "暂无换班申请记录"}

        results = []
        for swap in swaps:
            role = "发起方" if swap.requester_id == personnel.id else "接收方"
            results.append(
                {
                    "swap_id": swap.id,
                    "role": role,
                    "status": swap.get_status_display(),
                    "requester": swap.requester.name,
                    "target": swap.target_personnel.name,
                    "duty_date": str(swap.original_schedule.duty_date),
                    "reason": swap.reason,
                    "created_at": swap.created_at.strftime("%Y-%m-%d %H:%M"),
                }
            )

        return {
            "found": True,
            "count": len(results),
            "swaps": results,
            "summary": f"共 {len(results)} 条换班申请",
        }

    def build_base_queryset(self):
        """返回未过滤的换班申请 QuerySet"""
        return ScheduleSwapRequest.objects.select_related(
            "requester", "target_personnel", "original_schedule", "target_schedule"
        ).all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 相关的换班申请(发起或接收)"""
        personnel = getattr(ctx.user, "personnel", None)
        if personnel is None:
            return qs.none()
        return qs.filter(Q(requester=personnel) | Q(target_personnel=personnel))


# ---------------------------------------------------------------------------
# 工具 2: 发起换班申请
# ---------------------------------------------------------------------------


class SwapRequestCreateTool(BaseTool):
    """发起换班申请(require_confirmation=True,需要二次确认)"""

    name = "swap_request_create"
    description = "基于自然语言发起换班/替班申请(接收方决策后生效)"
    intent_type = "swap_request_create"
    risk_level = "write"
    require_confirmation = True

    def execute(self, query=None, context=None, **kwargs) -> dict:
        """发起换班申请"""
        ctx = context if isinstance(context, dict) else {}

        # dry_run 模式:返回 draft(不真正执行)
        if ctx.get("dry_run"):
            return self._dry_run(query, ctx)

        # confirmed 模式:真正执行
        if ctx.get("confirmed"):
            return self._confirmed(query, ctx)

        # 兜底(不应该走到这里,因为 orchestrator 会拦截)
        return {"found": False, "message": "工具执行异常:未进入 dry_run 或 confirmed 模式"}

    def _dry_run(self, query, ctx) -> dict:
        """dry_run 模式:解析 query,验证可行性,返 draft(不落库)"""
        user = ctx.get("user") if isinstance(ctx, dict) else None
        if user is None:
            return {"found": False, "message": "当前用户未关联人员档案"}
        requester = getattr(user, "personnel", None)
        if requester is None:
            return {"found": False, "message": "当前用户未关联人员档案"}

        params = extract_create_params(query, requester)
        if params is None:
            return {"found": False, "message": "无法识别换班意图,请明确换班对象(姓名)和日期"}

        target = Personnel.objects.filter(name=params.target_name).first()
        if target is None:
            return {"found": False, "message": f"未找到 '{params.target_name}' 该人员"}

        if target.id == requester.id:
            return {"found": False, "message": "不能把班换给自己"}

        duty_date = _parse_date_string(params.duty_date)
        if duty_date is None:
            return {"found": False, "message": f"无法解析日期 '{params.duty_date}'"}

        schedule = Schedule.objects.filter(duty_date=duty_date, duty_person=requester).first()
        if schedule is None:
            return {"found": False, "message": f"找不到您 {duty_date} 的排班记录"}

        return {
            "found": True,
            "draft": {
                "summary": f"为 {requester.name} → {target.name} {duty_date} 发起换班申请",
                "fields": {
                    "target_personnel_id": target.id,
                    "target_personnel_name": target.name,
                    "original_schedule_id": schedule.id,
                    "duty_date": duty_date.isoformat(),
                    "reason": params.reason,
                },
            },
        }

    def _confirmed(self, query, ctx) -> dict:
        """confirmed 模式:重 parse(query) → 调 swap_service.create_swap_by_query 落库"""
        user = ctx.get("user") if isinstance(ctx, dict) else None
        if user is None:
            return {"found": False, "message": "当前用户未关联人员档案"}
        requester = getattr(user, "personnel", None)
        if requester is None:
            return {"found": False, "message": "当前用户未关联人员档案"}

        params = extract_create_params(query, requester)
        if params is None:
            return {"found": False, "message": "无法识别换班意图"}

        duty_date = _parse_date_string(params.duty_date)
        if duty_date is None:
            return {"found": False, "message": f"无法解析日期 '{params.duty_date}'"}

        try:
            swap = create_swap_by_query(
                requester=requester,
                target_name=params.target_name,
                duty_date=duty_date,
                reason=params.reason,
            )
        except (SwapServiceError, SwapPermissionError) as e:
            return {"found": False, "message": str(e)}
        except Exception as e:
            return {"found": False, "message": f"创建换班申请失败: {e}"}

        return {
            "found": True,
            "result": {"swap_id": swap.id, "status": swap.status},
            "summary": (
                f"换班申请已发起: #{swap.id} "
                f"{swap.requester.name} → {swap.target_personnel.name} "
                f"{swap.original_schedule.duty_date}"
            ),
        }

    def build_base_queryset(self):
        """返回未过滤的换班申请 QuerySet"""
        return ScheduleSwapRequest.objects.all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 作为 requester 的换班申请"""
        personnel = getattr(ctx.user, "personnel", None)
        if personnel is None:
            return qs.none()
        return qs.filter(requester=personnel)


# ---------------------------------------------------------------------------
# 工具 3: 决策换班申请(接收方 accept/reject, 申请方 cancel)
# ---------------------------------------------------------------------------


class SwapRequestDecideTool(BaseTool):
    """对换班申请做出决策(require_confirmation=True,需要二次确认)"""

    name = "swap_request_decide"
    description = "对收到的换班申请做出决策(accept/reject/cancel)"
    intent_type = "swap_request_decide"
    risk_level = "write"
    require_confirmation = True

    def execute(self, query=None, context=None, **kwargs) -> dict:
        """对换班申请做出决策"""
        ctx = context if isinstance(context, dict) else {}

        # dry_run 模式:返回 draft(不真正执行)
        if ctx.get("dry_run"):
            return self._dry_run(query, ctx)

        # confirmed 模式:真正执行
        if ctx.get("confirmed"):
            return self._confirmed(query, ctx)

        # 兜底
        return {"found": False, "message": "工具执行异常:未进入 dry_run 或 confirmed 模式"}

    def _dry_run(self, query, ctx) -> dict:
        """dry_run 模式:解析 query,构造 draft,不真正执行"""
        # TODO: 实现自然语言解析(query → action, swap_id)
        # 暂时返回占位 draft
        return {
            "found": True,
            "draft": {
                "summary": f"将为以下操作发起确认: {query}",
                "fields": {"query": query, "note": "待实现:自然语言解析"},
            },
        }

    def _confirmed(self, query, ctx) -> dict:
        """confirmed 模式:真正执行落库"""
        # TODO: 实现业务逻辑(复用 SwapRequestViewSet.accept/reject/cancel)
        # 暂时返回占位结果
        return {
            "found": True,
            "result": "not_implemented",
            "summary": f"换班申请决策已完成(待实现): {query}",
        }

    def build_base_queryset(self):
        """返回未过滤的换班申请 QuerySet"""
        return ScheduleSwapRequest.objects.all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 作为 target 或 requester 的换班申请"""
        personnel = getattr(ctx.user, "personnel", None)
        if personnel is None:
            return qs.none()
        return qs.filter(Q(requester=personnel) | Q(target_personnel=personnel))
